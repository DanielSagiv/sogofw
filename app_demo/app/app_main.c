#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <glib-unix.h>
#include <unistd.h>
#include <errno.h>
#include <pthread.h>
#include <time.h>
#include <math.h>
#include <fcntl.h>
#include <string.h>
#include "gps.h"
#include "camera_imu.h"
#include "camera.h"
#include "ble_button.h"
#include "rpi_button.h"

#define BTN_PRESS_THRESHOLD      500
#define BTN_PRESS_DURATION_SHORT 2    // sec

#ifdef __linux__
#define BTN_TOUCH 0x14a
#else
#define BTN_TOUCH 0x1d  // Default value for non-Linux systems
#endif

// Function declarations
void get_time(char *time_buf);
void led_green_show(bool onoff);
void led_strip_show(bool onoff);
int get_adc_button(void);
void set_recording_state(bool state);
bool get_recording_state();
void *ble_button_thread(void *arg);
void *adc_button_thread(void *arg);
void initialize_camera_system(void);
void cleanup_camera_system(void);
void start_camera_recording(void);
void stop_camera_recording(void);
void *imu_acc_thread(void *arg);
void sig_handler(int sig);


// Global variables
pthread_mutex_t recording_mutex = PTHREAD_MUTEX_INITIALIZER;
bool recording = false;

void get_time(char *time_buf) {
    time_t currentTime;
    struct tm *timeInfo;
    time(&currentTime);
    timeInfo = localtime(&currentTime);
    strftime(time_buf, 20, "%m%d%Y-%H%M%S", timeInfo);
}

void led_green_show(bool onoff) {
    // Use Raspberry Pi GPIO for LED control
    static bool led_initialized = false;
    
    if (!led_initialized) {
        // Initialize GPIO for LED (using GPIO 17 as example)
        system("echo 17 | sudo tee /sys/class/gpio/export > /dev/null 2>&1");
        system("echo out | sudo tee /sys/class/gpio/gpio17/direction > /dev/null 2>&1");
        led_initialized = true;
    }
    
    if (onoff) {
        system("echo 1 | sudo tee /sys/class/gpio/gpio17/value > /dev/null 2>&1");
    } else {
        system("echo 0 | sudo tee /sys/class/gpio/gpio17/value > /dev/null 2>&1");
    }
}

void led_strip_show(bool onoff) {
    // Use Raspberry Pi GPIO for LED strip control
    static bool led_strip_initialized = false;
    
    if (!led_strip_initialized) {
        // Initialize GPIO for LED strip (using GPIO 27 as example)
        system("echo 27 | sudo tee /sys/class/gpio/export > /dev/null 2>&1");
        system("echo out | sudo tee /sys/class/gpio/gpio27/direction > /dev/null 2>&1");
        led_strip_initialized = true;
    }
    
    if (onoff) {
        system("echo 1 | sudo tee /sys/class/gpio/gpio27/value > /dev/null 2>&1");
    } else {
        system("echo 0 | sudo tee /sys/class/gpio/gpio27/value > /dev/null 2>&1");
    }
}

int get_adc_button(void) {
    // Use Raspberry Pi GPIO button instead of ADC
    static bool rpi_button_initialized = false;
    
    if (!rpi_button_initialized) {
        if (rpi_button_init() != 0) {
            printf("[get_adc_button]:[%d] Raspberry Pi button initialization failed\n", __LINE__);
            return -1;
        }
        rpi_button_initialized = true;
    }
    
    return rpi_button_is_pressed() ? 0 : 1000; // Return 0 if pressed, 1000 if not pressed
}

void set_recording_state(bool state) {
    pthread_mutex_lock(&recording_mutex);
    recording = state;
    pthread_mutex_unlock(&recording_mutex);
    if (state) {
        start_camera_recording();
        led_green_show(true);
    } else {
        stop_camera_recording();
        led_green_show(false);
    }
}

bool get_recording_state() {
    bool state = false;
    pthread_mutex_lock(&recording_mutex);
    state = recording;
    pthread_mutex_unlock(&recording_mutex);
    return state;
}

void *ble_button_thread(void *arg) {
    // BLE button disabled - not needed for Raspberry Pi
    while (1) {
        usleep(1000000);  // Sleep for 1 second
    }
    return NULL;
}

void *adc_button_thread(void *arg) {
    time_t press_time = 0;
    int adc_val;
    
    while (1) {
        adc_val = get_adc_button();
        
        if ((adc_val != -1) && (adc_val < BTN_PRESS_THRESHOLD)) {
            // Button is pressed
            if (press_time == 0) {
                // Start timing
                press_time = time(NULL);
            }
            printf("ADC Button press detected.\n");
        } else {
            // Button released/Error
            if (press_time != 0) {
                time_t elapsed = time(NULL) - press_time;
                
                if (elapsed <= BTN_PRESS_DURATION_SHORT) {
                    // Short press detected
                    printf("ADC Button SHORT press detected.\n");
                
                    // Reset recording state    
                    set_recording_state(!get_recording_state());
                } else {
                    // Long press detected
                    printf("ADC Button LONG press detected.\n");
                    // Stop recording if it's ongoing
                    if (get_recording_state()) {
                        set_recording_state(false);
                    } 
                    
                    printf("Shutting down the system in 10 seconds.\n");
                    system("sleep 10 && shutdown -h now &");

                }
            }
            
            press_time = 0;
        }

        usleep(100000);  // 100ms polling interval
    }
    return NULL;
}

void initialize_camera_system() {
    // Nothing to initialize - we'll start fresh each time
    printf("Camera system ready.\n");
}

void start_camera_recording() {
    // Kill any existing instances first
    system("pkill -f cam_skel-record.py");
    usleep(200000);  // Wait for cleanup
    
    char time_buf[30];
    get_time(time_buf);
    char command[256];
    snprintf(command, sizeof(command), 
        "python3.11 ./camera/cam_skel-record.py %s --action start &",
        time_buf);
    system(command);
    printf("Recording started.\n");
}

void stop_camera_recording() {
    system("pkill -f cam_skel-record.py");
    usleep(200000);  // 200ms delay
    printf("Recording stopped.\n");
}

void cleanup_camera_system() {
    stop_camera_recording();
    printf("Camera system cleaned up.\n");
}

void *imu_acc_thread(void *arg) {
    int ret;
    float xy;
    float acc_last = 0;
    float acc_sum = 0;
    float acc_derta;
    int sample_times = 10;
    u8 trigger_count = 0;

    while (1) {
        acc_sum = 0;
        for (int i = 0; i < sample_times; i++) {
            ret = bno055_get_accxy(&xy);
            if (ret == 0) {
                acc_sum += xy;
                usleep(100 * 1000);
            }
        }
        /*
        acc_derta = acc_sum/sample_times - acc_last;
        acc_last = acc_sum/sample_times;
        fabs(acc_derta) > 5 ? trigger_count++ : (trigger_count = 0);
        if (trigger_count >= 3) {
            trigger_count = 0;
            if (!get_recording_state()) {
                set_recording_state(true);
                sleep(30);
            }
        }*/
    }
    return NULL;
}

void sig_handler(int sig) {
    if (sig == SIGINT) {
        printf("Received SIGINT, stopping recording and exiting...\n");
        set_recording_state(false);
        cleanup_camera_system();
        exit(0);
    }
}

int main(int argc, char *argv[]) {
    int ret;
    int gps_port;
    int gps_fd;
    int imu_fd;
    pthread_t ble_tid, imu_tid, adc_tid = 0;
    char gps_data[256];
    char imu_data[256];
    char time_buf[30];
    char file_name[80];

    signal(SIGINT, sig_handler);
    
    led_green_show(false);
    initialize_camera_system();
    camera_imu_start();
    gps_port = gps_open();
    led_strip_show(true);
    get_time(time_buf);

    if (pthread_create(&ble_tid, NULL, ble_button_thread, NULL)) {
        printf("Create button pthread failed\n");
        return -1;
    }
    pthread_detach(ble_tid);

    if (pthread_create(&imu_tid, NULL, imu_acc_thread, NULL)) {
        printf("Create IMU pthread failed\n");
        return -1;
    }
    pthread_detach(imu_tid);

    if (pthread_create(&adc_tid, NULL, adc_button_thread, NULL)) {
        printf("Create ADC pthread failed\n");
        return -1;
    }
    pthread_detach(adc_tid);

    while (1) {

        if (get_recording_state()) {
            // Open GPS and IMU files
            get_time(time_buf);
            sprintf(file_name, "/mnt/sdcard/gps_%s.csv", time_buf);
            gps_fd = creat(file_name, 0666);
            sprintf(file_name, "/mnt/sdcard/imu_%s.csv", time_buf);
            imu_fd = creat(file_name, 0666);

            // Record loop
            while (get_recording_state()) {
                ret = gps_outdata(gps_port, gps_data, sizeof(gps_data));
                if (ret > 0) {
                    ret = write(gps_fd, gps_data, ret);
                    printf("Gps:%d ", ret);
                }
                usleep(300 * 1000);

                ret = camera_imu_get_data(imu_data, sizeof(imu_data));
                if (ret > 0) {
                    ret = write(imu_fd, imu_data, ret);
                    printf("Imu:%d ", ret);
                }

                usleep(100 * 1000);
            }

            // Close GPS and IMU files
            close(gps_fd);
            close(imu_fd);
        }
    }

    // Cleanup code
    led_strip_show(false);
    gps_close(gps_port);
    camera_imu_stop();
    cleanup_camera_system();

    return 0;
}

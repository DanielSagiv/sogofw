#include "rpi_button.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <stdbool.h>

#define GPIO_PATH "/sys/class/gpio"
#define GPIO_EXPORT "/sys/class/gpio/export"
#define GPIO_DIRECTION "/sys/class/gpio/gpio%d/direction"
#define GPIO_VALUE "/sys/class/gpio/gpio%d/value"
#define GPIO_PIN 17  // GPIO 17 - matches your working gpiozero test

static bool gpio_initialized = false;

int rpi_button_init(void) {
    FILE *fp;
    char path[256];
    
    // Export GPIO pin
    fp = fopen(GPIO_EXPORT, "w");
    if (fp == NULL) {
        printf("Error: Cannot open GPIO export\n");
        return -1;
    }
    fprintf(fp, "%d", GPIO_PIN);
    fclose(fp);
    
    // Wait a moment for the export to take effect
    usleep(100000); // 100ms
    
    // Set direction to input
    snprintf(path, sizeof(path), GPIO_DIRECTION, GPIO_PIN);
    fp = fopen(path, "w");
    if (fp == NULL) {
        printf("Error: Cannot set GPIO %d direction\n", GPIO_PIN);
        return -1;
    }
    fprintf(fp, "in");
    fclose(fp);
    
    // Set pull-up (write "up" to the active_low file)
    snprintf(path, sizeof(path), "/sys/class/gpio/gpio%d/active_low", GPIO_PIN);
    fp = fopen(path, "w");
    if (fp != NULL) {
        fprintf(fp, "0"); // Active low
        fclose(fp);
    }
    
    gpio_initialized = true;
    printf("Raspberry Pi button initialized on GPIO %d using sysfs\n", GPIO_PIN);
    return 0;
}

void rpi_button_cleanup(void) {
    if (!gpio_initialized) {
        return;
    }
    
    // Unexport GPIO pin
    FILE *fp = fopen(GPIO_EXPORT, "w");
    if (fp != NULL) {
        fprintf(fp, "%d", GPIO_PIN);
        fclose(fp);
    }
    
    gpio_initialized = false;
    printf("Raspberry Pi button cleaned up\n");
}

int rpi_button_read(void) {
    if (!gpio_initialized) {
        return -1;
    }
    
    FILE *fp;
    char path[256];
    char value[2];
    
    snprintf(path, sizeof(path), GPIO_VALUE, GPIO_PIN);
    fp = fopen(path, "r");
    if (fp == NULL) {
        return -1;
    }
    
    if (fgets(value, 2, fp) != NULL) {
        fclose(fp);
        return atoi(value);
    }
    
    fclose(fp);
    return -1;
}

bool rpi_button_is_pressed(void) {
    int value = rpi_button_read();
    return (value == 0); // Active low (button pressed = 0)
} 
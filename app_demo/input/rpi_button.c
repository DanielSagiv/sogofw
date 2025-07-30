#include "rpi_button.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <stdbool.h>
#include <gpiod.h>

#define CHIP_NAME "gpiochip0"
#define GPIO_PIN 17  // GPIO 17 - matches your working gpiozero test

static bool gpio_initialized = false;
static struct gpiod_chip *chip = NULL;
static struct gpiod_line *line = NULL;

int rpi_button_init(void) {
    // Open GPIO chip
    chip = gpiod_chip_open_by_name(CHIP_NAME);
    if (chip == NULL) {
        printf("Error: Cannot open GPIO chip '%s'\n", CHIP_NAME);
        return -1;
    }
    
    // Get GPIO line
    line = gpiod_chip_get_line(chip, GPIO_PIN);
    if (line == NULL) {
        printf("Error: Cannot get GPIO line %d\n", GPIO_PIN);
        gpiod_chip_close(chip);
        chip = NULL;
        return -1;
    }
    
    // Configure line as input with pull-up
    int ret = gpiod_line_request_input_flags(line, "rpi_button", 
                                           GPIOD_LINE_REQUEST_FLAG_BIAS_PULL_UP);
    if (ret < 0) {
        printf("Error: Cannot configure GPIO line %d as input\n", GPIO_PIN);
        gpiod_chip_close(chip);
        chip = NULL;
        line = NULL;
        return -1;
    }
    
    gpio_initialized = true;
    printf("Raspberry Pi button initialized on GPIO %d using gpiod\n", GPIO_PIN);
    return 0;
}

void rpi_button_cleanup(void) {
    if (!gpio_initialized) {
        return;
    }
    
    if (chip != NULL) {
        gpiod_chip_close(chip);
        chip = NULL;
    }
    
    line = NULL;
    gpio_initialized = false;
    printf("Raspberry Pi button cleaned up\n");
}

int rpi_button_read(void) {
    if (!gpio_initialized || line == NULL) {
        return -1;
    }
    
    int value = gpiod_line_get_value(line);
    return value;
}

bool rpi_button_is_pressed(void) {
    int value = rpi_button_read();
    return (value == 0); // Active low (button pressed = 0)
} 
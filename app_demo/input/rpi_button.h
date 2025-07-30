#ifndef RPI_BUTTON_H
#define RPI_BUTTON_H

#include <stdbool.h>

int rpi_button_init(void);
void rpi_button_cleanup(void);
int rpi_button_read(void);
bool rpi_button_is_pressed(void);

#endif // RPI_BUTTON_H 
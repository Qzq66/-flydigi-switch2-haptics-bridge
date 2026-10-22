#pragma once
#include <stdbool.h>
#include <stdint.h>
void virtual_spi_init(void);
bool virtual_spi_read(uint32_t address,uint8_t *buffer,uint8_t size);

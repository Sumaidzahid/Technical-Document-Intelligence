# TDI Dataset

## Dataset Overview

The initial dataset consists of **30 semiconductor datasheets** across three component categories.

- 30 datasheets initially.
- 10 microcontrollers.
- 10 operational amplifiers.
- 10 voltage regulators.
- 24 core documents and 6 challenge documents.
- Prioritise official manufacturer-hosted PDF documents.
- Maintain a central dataset inventory.
- Include multiple manufacturers and document formats.
- Preserve original PDFs and document revision information.

## Component Categories

### 1. Microcontrollers

Target specifications:

- CPU architecture and clock frequency
- Flash and RAM capacity
- Operating voltage
- GPIO count and peripheral interfaces
- ADC resolution and channel count
- Operating temperature range
- Package and pin information

### 2. Operational Amplifiers

Target specifications:

- Gain bandwidth product
- Input offset voltage
- Slew rate
- Input bias current
- Supply voltage range
- Input common-mode voltage range
- Output voltage swing
- Input and output characteristics

### 3. Voltage Regulators

Target specifications:

- Input voltage range
- Output voltage and adjustability
- Maximum output current
- Dropout voltage (where applicable)
- Efficiency (where applicable)
- Quiescent current
- Line regulation
- Load regulation
- Thermal and current protection

## Manufacturers

- STMicroelectronics
- Espressif
- Microchip Technology
- Raspberry Pi
- Texas Instruments
- Analog Devices
- Diodes Incorporated

## Dataset Selection Criteria

Datasheets should:

- Come from official manufacturer sources.
- Contain meaningful technical specifications and electrical-characteristics tables.
- Represent different document layouts and structures.
- Cover different component families and specification conventions.
- Include both straightforward and challenging documents.
- Prefer text-based PDFs for the initial collection, while retaining selected complex documents for robustness testing.

## Dataset Inventory

Maintain the following metadata for every document:

- Component name and exact part number
- Component category
- Manufacturer
- Datasheet title
- Document revision
- Publication date, where available
- Official PDF URL
- Page count
- File size
- Text-extraction status
- Dataset classification (core or challenge)

## Data Integrity

- Preserve original manufacturer PDFs without modification.
- Do not silently replace older revisions with newer ones.
- Record extraction failures separately from missing specifications.
- Retain source document and page references for extracted values.
- Keep extracted values traceable to their original evidence.

## Initial Objective

Establish a representative, reproducible dataset for developing and evaluating the Technical Document Intelligence (TDI) system.
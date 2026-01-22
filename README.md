# christine-machine
## Overview

This project is a modular image-processing machine with a minimal black GUI, built for visual artists and graphic designers who want to quickly generate original or heavily effected images. It is intended for rapid experimentation and batch processing, producing assets that can later be refined in tools like Photoshop or DaVinci Resolve.

Rather than a traditional layer-based editor, the system focuses on chaining discrete processing components into a reusable pipeline.

## Core Concept

Images are processed by passing them through a sequence of modular “boxes,” each representing a single effect or operation. These boxes can be added, removed, reordered, and configured interactively. The result can be previewed live, then applied to individual images or entire folders in batch.

The pipeline behaves like a machine: images go in, a defined sequence of operations runs, and processed images come out.

## Features

Minimal, distraction-free black GUI

Modular, reorderable effect pipeline

Live preview of the full processing chain

Batch processing of images

Background processing mode

Folder-based rules for automated workflows

Effects and Operations

Supported operations include, but are not limited to:
* Noise-based effects
Blur and diffusion

Pixelation and resolution distortion

Halo and glow-style outline effects

Automatic background removal

Custom masking

Optional image upscaling or downscaling

Effects can be combined in arbitrary sequences to produce unconventional or experimental results.

Automation and Rules

The application supports rule-based processing tied to folders. Images placed into a specific directory can automatically be processed using a predefined pipeline, enabling hands-off workflows and rapid iteration.

This makes it suitable for generating large volumes of assets with consistent transformations.

Intended Use

This tool is explicitly not a full image editor. There is no planned support for:

Layer-based composition

Transform tools (move, rotate, scale per element)

Manual painting or retouching

It is designed as a fast, first-stage processing step to save time before moving into more complex editing software.

Target Users

Visual artists

Graphic designers

Motion designers preparing assets

Anyone needing fast, repeatable image transformations without manual editing

# Bambu Lab A-Series Multi-Color Printing and Filament Selector Guide

## How Bambu Lab A-Series Achieves Multi-Color Printing Beyond 4 Colors

### Basic Architecture

Bambu Lab A-Series printers (such as A1, A1 mini) support multi-color printing through the AMS (Automatic Material System). In standard configuration:

- **Single AMS**: Supports 4-color printing
- **AMS Hub**: Expands capability to up to 16 colors by connecting multiple AMS units

### Solutions for 5~16 Color Printing

#### 1. Hardware Connection Setup

To achieve multi-color printing beyond 4 colors on A-Series printers, the following components are required:

| Color Count | Required Equipment |
|-------------|-------------------|
| 4 colors | 1 AMS unit |
| 8 colors | 2 AMS units + AMS Hub |
| 12 colors | 3 AMS units + AMS Hub |
| 16 colors | 4 AMS units + AMS Hub |

#### 2. The Role of AMS Hub (Filament Selector/Hub)

The AMS Hub is the core component connecting multiple AMS units to the printer:

- **Signal Routing**: Distributes control signals from the printer to each AMS unit
- **Filament Selection**: Automatically selects the appropriate filament from the corresponding AMS based on current printing requirements
- **Buffer Management**: Coordinates feeding and retracting operations between multiple AMS units

#### 3. Workflow

1. **Slicing Preparation**: Configure multi-color models in Bambu Studio, assigning each color to specific AMS slots
2. **Print Initiation**: The printer sends selection signals to the corresponding AMS through the AMS Hub
3. **Dynamic Switching**: When color changes are needed, the AMS Hub switches to the target AMS and executes retract/feed operations
4. **Coordinated Operation**: Multiple AMS units work in rotation to achieve seamless multi-color printing

#### 4. Firmware Requirements

- A-Series printers require firmware version **01.07.00.00** or higher
- Supports any combination of AMS/AMS 2 Pro/AMS HT
- **Note**: Not compatible with AMS lite in mixed configurations

---

## Filament Selector Retainer/Limiter

### Problem Description

When using the AMS Hub (filament selector), users frequently encounter **filament jamming** issues:

- PTFE tubes not inserted fully or at incorrect angles
- Filament bending or deviating when entering the selector
- Frequent jams causing print interruptions and reduced success rates

### Solution: PTFE Tube Retainer

#### Device Function

The retainer is a 3D-printed accessory designed to:

1. **Secure PTFE Tubes**: Ensure tubes are inserted into the selector at the correct angle and depth
2. **Prevent Deviation**: Restrict horizontal and vertical movement of the tubes
3. **Reduce Friction**: Maintain smooth filament passage through the selector inlet

#### Installation Recommendations

1. **Tube Preparation**:
   - Use a tube cutter to make strictly perpendicular cuts on PTFE tubes
   - Ensure clean, burr-free cuts
   - Insert tubes firmly to full depth during installation

2. **Device Installation**:
   - Secure the retainer at the selector inlet position
   - Ensure PTFE tubes pass through the guide holes of the retainer
   - Adjust positioning to maintain natural straight alignment of tubes

#### Advanced Optimization

If filament jamming persists after installing the retainer, consider the following modification:

- **Polish the Selector Interior**: Grind the flat exit surface in the center of the removable magnet-equipped plastic cylinder in the upper half of the selector from flat to a 45-degree bevel, reducing resistance for filament passage

### Reference Resources

- MakerWorld Model Page: [PTFE Tube Retainer](https://makerworld.com.cn/zh/models/1731317)
- Recommended Print Settings: 0.2mm layer height, 2 walls, 15% infill

### Important Notes

- Installation may require powering off the printer and disconnecting cables and tubes
- Some retainer designs require support structures
- Best results are achieved when used in combination with a top mounting bracket

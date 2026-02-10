# RT Slab Stacking Algorithm

## Overview

The RT (Reflectance-Transmittance) Slab Stacking Algorithm is a physical model for predicting the color appearance of stacked semi-transparent materials. This algorithm is widely used in multi-color 3D printing color mixing prediction, paint layer simulation, and related fields.

Unlike the Kubelka-Munk theory, this algorithm adopts an **incoherent slab superposition** approach. It predicts the final color by calculating the effective reflectance (R) and transmittance (T) of each layer, combined with multiple-reflection adding principles.

## Core Principles

### 1. Slab Model

Each material layer is treated as a thin slab with effective optical parameters:

- **Reflectance (r)**: The proportion of light reflected at the layer's internal surface
- **Transmittance (t)**: The proportion of light passing through the layer

For each material layer, the parameterization is expressed as:

```
r = sigmoid(α)                          # Reflectance parameter
t = sigmoid(β) × (1 - r)                # Transmittance parameter
```

Where:
- `α` (alpha): Log-odds parameter for reflectance
- `β` (beta): Log-odds parameter for transmittance
- The `sigmoid` function ensures: 0 ≤ r ≤ 1, 0 ≤ t ≤ 1-r

### 2. Layer Adding Formula

When multiple material layers are stacked, the following recursive formula is used to calculate the overall reflectance:

```
R_next = r + (t² × R_prev) / (1 - r × R_prev)
```

Where:
- `R_prev`: Reflectance of the previous layer (or backing)
- `R_next`: Total reflectance after adding the current layer
- `r, t`: Reflectance and transmittance of the current layer

This formula accounts for multiple reflection effects between layers.

### 3. Backing Treatment

The reflectance of the bottom layer (backing) `Rb` is also parameterized using sigmoid:

```
Rb = sigmoid(γ)
```

Where `γ` (gamma) is the backing reflectance parameter.

## Algorithm Workflow

### Phase 1: Parameter Fitting

1. **Data Preparation**
   - Collect known recipes (material layer sequences) and their measured colors
   - Convert RGB measurements to CIE Lab color space

2. **Parameter Initialization**
   - Initialize `α ≈ -3.0` for each material (low reflectance)
   - Initialize `β ≈ 3.0` (high transmittance)
   - Initialize backing `γ ≈ 1.0` (Rb ≈ 0.73)

3. **Optimization Fitting**
   - Use least squares method to optimize parameters
   - Calculate differences between predicted and measured colors in Lab space
   - Employ Huber loss function for robustness
   - Add L2 regularization to prevent overfitting

### Phase 2: Color Prediction

1. **Layer Sequence Parsing**
   - Convert material sequences to index matrices
   - Support two orders: top-first or bottom-first

2. **Layer-by-Layer Calculation**
   - Start from the backing and add each layer sequentially
   - Apply the layer adding formula to update total reflectance

3. **Color Conversion**
   - Convert linear reflectance to sRGB space
   - Output the final predicted color

## Mathematical Details

### Sigmoid Function

```python
sigmoid(x) = 1 / (1 + exp(-x))
```

To prevent numerical overflow, inputs are typically clamped to the range [-20, 20].

### Color Space Conversions

1. **sRGB → Linear RGB**
   ```
   If sRGB ≤ 0.04045:
       linear = sRGB / 12.92
   Else:
       linear = ((sRGB + 0.055) / 1.055)^2.4
   ```

2. **Linear RGB → sRGB**
   ```
   If linear ≤ 0.0031308:
       sRGB = linear × 12.92
   Else:
       sRGB = (1.055 × linear^(1/2.4)) - 0.055
   ```

3. **RGB → Lab**
   - First convert to XYZ color space
   - Then convert to CIE Lab space
   - Use Delta E CIE76 to calculate color differences

### Loss Function

```
Loss = Σ(ΔE) + λ × ||parameters||²
```

Where:
- `ΔE`: CIE76 color difference between predicted and measured colors
- `λ`: Regularization coefficient (typically 1e-3)
- `||parameters||²`: L2 norm of the parameter vector

## Two Parameter Modes

### 1. Layer-Independent Mode

Each material has only one set of parameters `(α, β)`, independent of layer position.

- **Advantages**: Fewer parameters, less prone to overfitting
- **Disadvantages**: Cannot capture layer position effects on optical properties

### 2. Layer-Dependent Mode

Each material has independent parameters `(α_l, β_l)` at each layer position.

- **Advantages**: More flexible, can model layer position effects
- **Disadvantages**: More parameters, requires more training data

## Application Scenarios

### Multi-Color 3D Printing

In 3D printing, new colors are created by stacking thin layers of different colors:

1. **Calibration Phase**: Print color charts, measure actual colors, fit material parameters
2. **Prediction Phase**: Input target color, algorithm predicts required layer sequence
3. **Print Execution**: Print each layer according to the predicted sequence

### Paint/Ink Layer Stacking

Predict the final color effect of multi-layer paint or ink coatings.

## Implementation Notes

1. **Numerical Stability**
   - The denominator `1 - r × R` needs a minimum clamp (e.g., 1e-6) to prevent division by zero
   - Reflectance results should be clamped to [0, 1] range

2. **Floating Point Precision**
   - Use float64 for parameter optimization to maintain finite-difference sensitivity
   - Final output can be converted to float32

3. **Empty Layer Handling**
   - Define a special material "EMPTY" to represent no material
   - EMPTY layer parameters are fixed at: r = 0, t = 1 (fully transparent)

## References

- Implementation code: `py_module/prototypes/src/oc_prototypes_02/calib_color_model_fit_01/rt_stack_fit_eval.py`
- Related theory: Adding-doubling method for radiative transfer

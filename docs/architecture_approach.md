# TrailPrint3D Web Application Architecture Approach

This document outlines the technical approach for converting the TrailPrint3D Blender addon into a self-hosted web application.

## Overview

The goal is to provide a seamless web experience for users to upload GPX files, configure settings, preview a 3D printable terrain map, and export the final model. The primary technical challenge involves bridging a modern web frontend with the heavy-duty 3D processing capabilities of Blender.

We evaluate two primary approaches for handling the 3D processing and preview generation.

---

## Approach A: Full Headless-Blender Wrapper (Chosen Approach)

In this approach, a FastAPI backend orchestrates operations using the official headless Blender Python module (`bpy==5.0.1`).

**Workflow:**
1. **Quick Preview:** The user uploads a GPX file. FastAPI immediately dispatches a job to a dedicated lightweight `bpy` function. This function creates a decimated, low-poly version of the terrain and track. It exports this as a lightweight `.glb` (glTF) file.
2. **Real-time Updates:** When the user changes settings (e.g., shape, scale), new preview jobs are triggered, returning updated `.glb` files to the frontend.
3. **Final Export:** Once the user is satisfied, they request a final export. A separate, high-priority background job (via RQ) executes the full, high-resolution TrailPrint3D pipeline via `bpy` to generate STL, OBJ, or 3MF files.

**Pros:**
- **Single Source of Truth:** We reuse the exact same terrain generation, pathing, and shaping logic from the original TrailPrint3D addon for both preview and export.
- **High Fidelity:** The preview exactly matches the final export (just at a lower resolution).
- **Simpler Stack:** Only requires Python 3.11 and the `bpy` module; no need for duplicate Python geometry libraries (like `trimesh` or `shapely`) to simulate Blender's modifiers.

**Cons:**
- **Overhead:** `bpy` has a larger memory footprint and startup overhead compared to pure Python processing.
- **Scalability Challenges:** Requires careful process management, as `bpy` isn't designed for highly concurrent async web requests in a single process. (Mitigated by using background workers and job queues).

---

## Approach B: Hybrid (Custom Python-for-Preview + Blender-for-Export)

In this approach, the backend uses lightweight Python geospatial and geometry libraries to generate the quick preview, while reserving headless Blender only for the final export.

**Workflow:**
1. **Quick Preview:** FastAPI processes the GPX file using `geopandas`, `rasterio` (for elevation), and `trimesh`. It quickly extrudes a simple mesh and sends a JSON or `.glb` to the frontend.
2. **Real-time Updates:** Fast, pure-Python logic recalculates and returns the preview.
3. **Final Export:** A background job spins up a headless Blender instance to run the original TrailPrint3D logic.

**Pros:**
- **Speed:** Instant previews without the overhead of the `bpy` module.
- **Resource Efficiency:** Lower memory usage for the API server.

**Cons:**
- **Code Duplication:** We must essentially rewrite the complex logic for terrain shaping, track extrusion, and feature placement (buildings, rivers) in pure Python just for the preview.
- **Visual Discrepancy:** The Python preview mesh will likely look subtly different from the final Blender export due to different algorithms (e.g., Blender's boolean modifiers vs. Python libraries).
- **Maintenance Burden:** Any new features added to the Blender logic must also be ported to the Python preview logic.

---

## Conclusion and Recommended Architecture

We strongly recommend and have chosen **Approach A (Full Headless-Blender Wrapper)**.

The complexity of TrailPrint3D's features (multiple shapes, bevels, single-color modes, intricate boolean operations for magnets/dovetails) relies heavily on Blender's robust modifier stack and operators. Attempting to replicate this in pure Python (Approach B) would introduce a massive maintenance burden and lead to inevitable visual discrepancies between the preview and the final print.

By leveraging `bpy==5.0.1` directly within Python 3.11, we maintain a single, consistent logic base. We mitigate the performance concerns of Approach A by:
1. Using an RQ (Redis Queue) background worker system to isolate `bpy` processing from the fast API server.
2. Specifically authoring a fast "preview mode" within the `bpy` script that relies on decimation and lower resolution elevation data to return quick `.glb` assets to the frontend's Three.js canvas.

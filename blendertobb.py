bl_info = {
    "name": "Blockbench .bbmodel Exporter",
    "author": "Expert Developer",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Export > Blockbench (.bbmodel)",
    "description": "Exports selected meshes to Blockbench .bbmodel format with Hytale-compatible orientation.",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export",
}

import bpy
import json
import os
import math
from mathutils import Vector
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

class EXPORT_OT_bbmodel(Operator, ExportHelper):
    """Export selected objects to .bbmodel file"""
    bl_idname = "export_scene.bbmodel"
    bl_label = "Export to Blockbench (.bbmodel)"
    bl_options = {'PRESET', 'UNDO'}

    # File extension filter
    filename_ext = ".bbmodel"
    filter_glob: StringProperty(
        default="*.bbmodel",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        return self.write_bbmodel(context, self.filepath)

    def write_bbmodel(self, context, filepath):
        objects = context.selected_objects
        
        if not objects:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        # JSON Structure for .bbmodel
        bb_data = {
            "meta": {
                "format_version": "4.0",
                "model_format": "free", # Free model format allows arbitrary rotations
                "box_uv": False
            },
            "name": os.path.basename(filepath),
            "elements": [],
            "outliner": []
        }

        # Coordinate conversion function (Blender -> Blockbench)
        # Mapping: Blender X (Front) -> BB Z (South)
        # Mapping: Blender Y (Side)  -> BB X (East)
        # Mapping: Blender Z (Up)    -> BB Y (Up)
        def to_bb_space(vec_meters):
            # Convert 1 Blender Unit to 16 Pixels
            x = vec_meters.y * 16
            y = vec_meters.z * 16
            z = vec_meters.x * 16
            return [x, y, z]

        for obj in objects:
            if obj.type != 'MESH':
                continue
            
            # 1. Get Scale and Calculate Local Bounding Box
            # Blender's bound_box is unscaled, so we multiply by obj.scale
            scale = obj.scale
            bbox_corners = [Vector(corner) for corner in obj.bound_box]
            
            # Apply scale to local corners
            scaled_corners = []
            for v in bbox_corners:
                scaled_v = Vector((v.x * scale.x, v.y * scale.y, v.z * scale.z))
                scaled_corners.append(scaled_v)
            
            # Find min/max in local space (scaled)
            l_min = Vector((min(c[0] for c in scaled_corners), min(c[1] for c in scaled_corners), min(c[2] for c in scaled_corners)))
            l_max = Vector((max(c[0] for c in scaled_corners), max(c[1] for c in scaled_corners), max(c[2] for c in scaled_corners)))

            # 2. Calculate Origin and Absolute Position
            # Blockbench 'from'/'to' must be absolute coordinates before rotation.
            # Formula: Object World Location + Local Offset
            loc = obj.location
            
            world_min = loc + l_min
            world_max = loc + l_max
            
            # 3. Convert to Blockbench Coordinate System
            bb_from_raw = to_bb_space(world_min)
            bb_to_raw   = to_bb_space(world_max)
            bb_origin   = to_bb_space(loc) # This is the Pivot Point

            # Sort min/max because axis swapping might invert the order
            bb_from = [min(bb_from_raw[i], bb_to_raw[i]) for i in range(3)]
            bb_to   = [max(bb_from_raw[i], bb_to_raw[i]) for i in range(3)]

            # 4. Convert Rotation (Euler -> Degrees & Axis Swap)
            # Mapping: Blender (X, Y, Z) -> Blockbench (Y, Z, X)
            rot = obj.rotation_euler
            bb_rot = [math.degrees(rot.y), math.degrees(rot.z), math.degrees(rot.x)]

            # Construct Element Dictionary
            element = {
                "name": obj.name,
                "from": bb_from,
                "to": bb_to,
                "origin": bb_origin, 
                "rotation": bb_rot,
                "autouv": 0,
                "faces": {
                    "north": {"uv": [0, 0, 1, 1], "texture": 0},
                    "east":  {"uv": [0, 0, 1, 1], "texture": 0},
                    "south": {"uv": [0, 0, 1, 1], "texture": 0},
                    "west":  {"uv": [0, 0, 1, 1], "texture": 0},
                    "up":    {"uv": [0, 0, 1, 1], "texture": 0},
                    "down":  {"uv": [0, 0, 1, 1], "texture": 0}
                }
            }
            bb_data["elements"].append(element)

        # Write to JSON file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(bb_data, f, indent=4)
            self.report({'INFO'}, f"Successfully exported: {filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

# Registration functions to add the tool to Blender's menu
def menu_func_export(self, context):
    self.layout.operator(EXPORT_OT_bbmodel.bl_idname, text="Blockbench (.bbmodel)")

def register():
    bpy.utils.register_class(EXPORT_OT_bbmodel)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(EXPORT_OT_bbmodel)

if __name__ == "__main__":
    register()
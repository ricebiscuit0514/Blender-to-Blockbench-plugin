bl_info = {
    "name": "Blockbench .bbmodel Exporter (Quaternion Swap)",
    "author": "Expert Developer",
    "version": (1, 6, 0),
    "blender": (3, 0, 0),
    "location": "File > Export > Blockbench (.bbmodel)",
    "description": "Exports perfectly by swapping quaternion components to avoid rotation flipping.",
    "warning": "",
    "category": "Import-Export",
}

import bpy
import json
import os
import math
from mathutils import Vector, Quaternion
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty
from bpy.types import Operator

class EXPORT_OT_bbmodel(Operator, ExportHelper):
    """Export using Quaternion Component Swapping (Fixes orientation flip)"""
    bl_idname = "export_scene.bbmodel_quat"
    bl_label = "Export to Blockbench (.bbmodel)"
    filename_ext = ".bbmodel"

    filter_glob: StringProperty(default="*.bbmodel", options={'HIDDEN'}, maxlen=255)

    def execute(self, context):
        return self.write_bbmodel(context, self.filepath)

    def write_bbmodel(self, context, filepath):
        objects = context.selected_objects
        if not objects:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        bb_data = {
            "meta": {
                "format_version": "4.0",
                "model_format": "free", 
                "box_uv": False
            },
            "name": os.path.basename(filepath),
            "elements": [],
            "outliner": []
        }

        # --- [Expert Logic] Quaternion Component Swap ---
        # Instead of converting Euler angles (which causes flipping),
        # we directly swap the internal Quaternion components.
        # Mapping: Blender(x,y,z) -> Blockbench(z,x,y)
        # Therefore: Quat X -> Quat Z, Quat Y -> Quat X, Quat Z -> Quat Y

        def get_swapped_rotation(obj):
            # 1. Get rotation as Quaternion (w, x, y, z)
            # Use 'matrix_world' decomposition to handle parented transforms correctly
            loc, rot_quat, scl = obj.matrix_world.decompose()
            
            # 2. Swap components to match the axis mapping
            # Blender X (Front) -> BB Z
            # Blender Y (Side)  -> BB X
            # Blender Z (Up)    -> BB Y
            # New Quat (w, x, y, z) = Old Quat (w, y, z, x)
            
            new_quat = Quaternion((rot_quat.w, rot_quat.y, rot_quat.z, rot_quat.x))
            
            # 3. Convert to Euler (Degrees) for Blockbench
            # Blockbench usually reads XYZ order.
            rot_euler = new_quat.to_euler('XYZ')
            
            return [
                math.degrees(rot_euler.x),
                math.degrees(rot_euler.y),
                math.degrees(rot_euler.z)
            ]

        def get_mapped_vector(vec):
            # Maps vector coordinates: x->z, y->x, z->y
            # Scale included (x16)
            return Vector((vec.y * 16, vec.z * 16, vec.x * 16))

        for obj in objects:
            if obj.type != 'MESH':
                continue
            
            # 1. Calculate Origin (Pivot)
            loc, _, _ = obj.matrix_world.decompose()
            bb_origin = get_mapped_vector(loc)

            # 2. Calculate Unrotated Local Dimensions
            # We must map the dimensions using the same logic (x->z, y->x, z->y)
            scale = obj.scale
            local_bbox = [Vector(corner) for corner in obj.bound_box]
            
            # Calculate raw local sizes
            x_raw = (max(v.x for v in local_bbox) - min(v.x for v in local_bbox)) * scale.x
            y_raw = (max(v.y for v in local_bbox) - min(v.y for v in local_bbox)) * scale.y
            z_raw = (max(v.z for v in local_bbox) - min(v.z for v in local_bbox)) * scale.z
            
            # Map dimensions to BB axes
            # Blender X size -> BB Z size
            # Blender Y size -> BB X size
            # Blender Z size -> BB Y size
            bb_size_x = y_raw * 16
            bb_size_y = z_raw * 16
            bb_size_z = x_raw * 16

            # 3. Calculate 'from' and 'to' relative to Origin
            # We assume the mesh is centered on its origin for the box calculation,
            # then offset it if the mesh data itself is offset.
            
            center_local = Vector((
                (min(v.x for v in local_bbox) + max(v.x for v in local_bbox)) / 2 * scale.x,
                (min(v.y for v in local_bbox) + max(v.y for v in local_bbox)) / 2 * scale.y,
                (min(v.z for v in local_bbox) + max(v.z for v in local_bbox)) / 2 * scale.z
            ))
            
            # Map offset: y->x, z->y, x->z
            center_offset_bb = Vector((center_local.y * 16, center_local.z * 16, center_local.x * 16))
            
            # Absolute position
            abs_center = bb_origin + center_offset_bb
            
            bb_from = [
                abs_center.x - bb_size_x / 2,
                abs_center.y - bb_size_y / 2,
                abs_center.z - bb_size_z / 2
            ]
            
            bb_to = [
                abs_center.x + bb_size_x / 2,
                abs_center.y + bb_size_y / 2,
                abs_center.z + bb_size_z / 2
            ]

            # 4. Get Rotation using Quaternion Swap
            bb_rotation = get_swapped_rotation(obj)

            element = {
                "name": obj.name,
                "from": bb_from,
                "to": bb_to,
                "origin": [bb_origin.x, bb_origin.y, bb_origin.z],
                "rotation": bb_rotation,
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

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(bb_data, f, indent=4)
            self.report({'INFO'}, f"Export Success: {os.path.basename(filepath)}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}

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

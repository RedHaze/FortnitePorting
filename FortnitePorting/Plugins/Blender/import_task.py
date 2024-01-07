import bpy
import os
import json
import re
import bmesh
import traceback
from enum import Enum
from math import radians
from mathutils import Matrix, Vector, Euler, Quaternion
from .ue_format import UEFormatImport, UEModelOptions, UEAnimOptions
from .logger import Log
from .server import MessageServer

class ERigType(Enum):
    DEFAULT = 0
    TASTY = 1

class ETextureExportTypes(Enum):
    DATA = 0
    PLANE = 1

class MappingCollection:
    def __init__(self, textures=(), scalars=(), vectors=(), switches=(), component_masks=()):
        self.textures = textures
        self.scalars = scalars
        self.vectors = vectors
        self.switches = switches
        self.component_masks = component_masks


class SlotMapping:
    def __init__(self, name, slot=None, alpha_slot=None, switch_slot=None, value_func=None, coords="UV0"):
        self.name = name
        self.slot = name if slot is None else slot
        self.alpha_slot = alpha_slot
        self.switch_slot = switch_slot
        self.value_func = value_func
        self.coords = coords

default_mappings = MappingCollection(
    textures=[
        SlotMapping("Diffuse"),
        SlotMapping("D", "Diffuse"),
        SlotMapping("Base Color", "Diffuse"),
        SlotMapping("Concrete", "Diffuse"),
        SlotMapping("Trunk_BaseColor", "Diffuse"),
        
        SlotMapping("Background Diffuse", alpha_slot="Background Diffuse Alpha"),
        SlotMapping("BG Diffuse Texture", "Background Diffuse", alpha_slot="Background Diffuse Alpha"),
        
        SlotMapping("M"),
        SlotMapping("Mask", "M"),
        
        SlotMapping("SpecularMasks"),
        SlotMapping("S", "SpecularMasks"),
        SlotMapping("SRM", "SpecularMasks"),
        SlotMapping("Specular Mask", "SpecularMasks"),
        SlotMapping("Concrete_SpecMask", "SpecularMasks"),
        SlotMapping("Trunk_Specular", "SpecularMasks"),
        
        SlotMapping("Normals"),
        SlotMapping("N", "Normals"),
        SlotMapping("Normal", "Normals"),
        SlotMapping("NormalMap", "Normals"),
        SlotMapping("ConcreteTextureNormal", "Normals"),
        SlotMapping("Trunk_Normal", "Normals"),
        
        SlotMapping("Emissive", "Emission"),
        SlotMapping("EmissiveTexture", "Emission"),
        
        SlotMapping("MaskTexture"),
        SlotMapping("OpacityMask", "MaskTexture")
    ],
    scalars=[
        SlotMapping("RoughnessMin", "Roughness Min"),
        SlotMapping("SpecRoughnessMin", "Roughness Min"),
        SlotMapping("RawRoughnessMin", "Roughness Min"),
        SlotMapping("RoughnessMax", "Roughness Max"),
        SlotMapping("SpecRoughnessMax", "Roughness Max"),
        SlotMapping("RawRoughnessMax", "Roughness Max"),
        SlotMapping("emissive mult", "Emission Strength")
    ],
    vectors=[
        SlotMapping("Skin Boost Color And Exponent", "Skin Color", alpha_slot="Skin Boost"),
        SlotMapping("SkinTint", "Skin Color", alpha_slot="Skin Boost"),
        SlotMapping("EmissiveMultiplier", "Emission Multiplier"),
        SlotMapping("Emissive Multiplier", "Emission Multiplier"),
        SlotMapping("Emissive Color", "Emission Color", switch_slot="Use Emission Color")
    ],
    switches=[
        SlotMapping("SwizzleRoughnessToGreen")
    ]
)

layer_mappings = MappingCollection(
    textures=[
        SlotMapping("Diffuse"),
        SlotMapping("SpecularMasks"),
        SlotMapping("Normals"),
        SlotMapping("EmissiveTexture"),

        SlotMapping("Diffuse_Texture_2"),
        SlotMapping("SpecularMasks_2"),
        SlotMapping("Normals_Texture_2"),
        SlotMapping("Emissive_Texture_2"),

        SlotMapping("Diffuse_Texture_3"),
        SlotMapping("SpecularMasks_3"),
        SlotMapping("Normals_Texture_3"),
        SlotMapping("Emissive_Texture_3"),

        SlotMapping("Diffuse_Texture_4"),
        SlotMapping("SpecularMasks_4"),
        SlotMapping("Normals_Texture_4"),
        SlotMapping("Emissive_Texture_4"),

        SlotMapping("Diffuse_Texture_5"),
        SlotMapping("SpecularMasks_5"),
        SlotMapping("Normals_Texture_5"),
        SlotMapping("Emissive_Texture_5"),

        SlotMapping("Diffuse_Texture_6"),
        SlotMapping("SpecularMasks_6"),
        SlotMapping("Normals_Texture_6"),
        SlotMapping("Emissive_Texture_6"),
    ]
)

toon_mappings = MappingCollection(
    textures=[
        SlotMapping("LitDiffuse"),
        SlotMapping("ShadedDiffuse"),
        SlotMapping("DistanceField_InkLines"),
        SlotMapping("InkLineColor_Texture"),
        SlotMapping("SSC_Texture"),
        SlotMapping("Normals")
    ],
    scalars=[
        SlotMapping("ShadedColorDarkening"),
        SlotMapping("FakeNormalBlend_Amt"),
        SlotMapping("PBR_Shading", "Use PBR Shading", value_func=lambda value: int(value))
    ],
    vectors=[
        SlotMapping("InkLineColor", "InkLineColor_Texture")
    ]
)

valet_mappings = MappingCollection(
    textures=[
        SlotMapping("Diffuse"),
        SlotMapping("Mask", alpha_slot="Mask Alpha"),
        SlotMapping("Decal", alpha_slot="Decal Alpha", coords="UV1"),
        SlotMapping("Normal"),
        SlotMapping("Specular Mask"),
        SlotMapping("Scratch/Grime/EMPTY"),
    ],
    scalars=[
        SlotMapping("Scratch Intensity"),
        SlotMapping("Grime Intensity"),
        SlotMapping("Grime Spec"),
        SlotMapping("Grime Roughness"),

        SlotMapping("Layer 01 Specular"),
        SlotMapping("Layer 01 Metalness"),
        SlotMapping("Layer 01 Roughness Min"),
        SlotMapping("Layer 01 Roughness Max"),
        SlotMapping("Layer 01 Clearcoat"),
        SlotMapping("Layer 01 Clearcoat Roughness Min"),
        SlotMapping("Layer 01 Clearcoat Roughness Max"),

        SlotMapping("Layer 02 Specular"),
        SlotMapping("Layer 02 Metalness"),
        SlotMapping("Layer 02 Roughness Min"),
        SlotMapping("Layer 02 Roughness Max"),
        SlotMapping("Layer 02 Clearcoat"),
        SlotMapping("Layer 02 Clearcoat Roughness Min"),
        SlotMapping("Layer 02 Clearcoat Roughness Max"),

        SlotMapping("Layer 03 Specular"),
        SlotMapping("Layer 03 Metalness"),
        SlotMapping("Layer 03 Roughness Min"),
        SlotMapping("Layer 03 Roughness Max"),
        SlotMapping("Layer 03 Clearcoat"),
        SlotMapping("Layer 03 Clearcoat Roughness Min"),
        SlotMapping("Layer 03 Clearcoat Roughness Max"),

        SlotMapping("Layer 04 Specular"),
        SlotMapping("Layer 04 Metalness"),
        SlotMapping("Layer 04 Roughness Min"),
        SlotMapping("Layer 04 Roughness Max"),
        SlotMapping("Layer 04 Clearcoat"),
        SlotMapping("Layer 04 Clearcoat Roughness Min"),
        SlotMapping("Layer 04 Clearcoat Roughness Max"),
    ],
    vectors=[
        SlotMapping("Scratch Tint"),
        SlotMapping("Grime Tint"),

        SlotMapping("Layer 01 Color"),
        SlotMapping("Layer 02 Color"),
        SlotMapping("Layer 03 Color"),
        SlotMapping("Layer 04 Color"),
    ]
)

glass_mappings = MappingCollection(
    textures=[
        SlotMapping("Color_DarkTint"),
        SlotMapping("Diffuse Texture", "Color"),
        SlotMapping("Normals"),
        SlotMapping("BakedNormal", "Normals"),
        SlotMapping("Diffuse Texture with Alpha Mask", "Color", alpha_slot="Mask")
    ],
    scalars=[
        SlotMapping("Specular"),
        SlotMapping("Metallic"),
        SlotMapping("Roughness"),
        SlotMapping("Window Tint Amount", "Tint Amount"),
        SlotMapping("Fresnel Exponent"),
        SlotMapping("Fresnel Inner Transparency"),
        SlotMapping("Fresnel Inner Transparency Max Tint"),
        SlotMapping("Fresnel Outer Transparency"),
        SlotMapping("Glass thickness", "Thickness"),
    ],
    vectors=[
        SlotMapping("ColorFront", "Color"),
        SlotMapping("Base Color", "Color"),
    ]
)

trunk_mappings = MappingCollection(
    textures=[
        SlotMapping("Trunk_BaseColor", "Diffuse"),
        SlotMapping("Trunk_Specular", "SpecularMasks"),
        SlotMapping("Trunk_Normal", "Normals"),
    ]
)

foliage_mappings = MappingCollection(
    textures=[
        SlotMapping("Diffuse"),
        SlotMapping("Normals"),
        SlotMapping("MaskTexture"),
    ],
    scalars=[
        SlotMapping("Roughness Leafs", "Roughness"),
        SlotMapping("Specular_Leafs", "Specular")
    ],
    vectors=[
        SlotMapping("Color1_Base"),
        SlotMapping("Color2_Lit"),
        SlotMapping("Color3_Shadows")
    ]
)

gradient_mappings = MappingCollection(
    textures=[
        SlotMapping("Diffuse"),
        SlotMapping("Layer Mask", alpha_slot="Layer Mask Alpha"),
        SlotMapping("SkinFX_Mask"),
        SlotMapping("Layer1_Gradient"),
        SlotMapping("Layer2_Gradient"),
        SlotMapping("Layer3_Gradient"),
        SlotMapping("Layer4_Gradient"),
        SlotMapping("Layer5_Gradient"),
    ],
    switches=[
        SlotMapping("use Alpha Channel as mask", "Use Layer Mask Alpha")
    ],
    component_masks=[
        SlotMapping("GmapSkinCustomization_Channel")
    ]
)

class ImportTask:
    def run(self, response):
        assets_folder = response.get("AssetsFolder")
        options = response.get("Options")

        append_data()
        
        datas = response.get("Data")
        for data in datas:
            DataImportTask(data, assets_folder, options)

class DataImportTask:
    def __init__(self, data, assets_folder, options):
        self.imported_materials = {}
        self.assets_folder = assets_folder
        self.options = options
        self.import_data(data)

    def import_data(self, data):
        print(json.dumps(data))
        self.name = data.get("Name")
        self.type = data.get("Type")
        self.override_materials = []
        self.override_parameters = []
        self.is_toon = False
        self.collection = bpy.context.scene.collection
        self.meshes = []
        self.imported_mesh_count = 0
        self.imported_meshes = []
        self.crunch_verts_materials = []
        self.rig_type = ERigType(self.options.get("RigType"))

        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode='OBJECT')

        import_type = data.get("PrimitiveType")
        match import_type:
            case "Mesh":
                self.import_mesh_data(data)
            case "Animation":
                self.import_anim_data(data)
            case "Texture":
                self.import_texture_data(data)
    def import_mesh_data(self, data):
        self.override_materials = data.get("OverrideMaterials")
        self.override_parameters = data.get("OverrideParameters")
        self.collection = create_collection(self.name) if self.options.get("ImportCollection") else bpy.context.scene.collection

        meshes = data.get("Meshes")
        if self.type in ["Outfit", "Backpack"]:
            meshes = data.get("OverrideMeshes")
            for mesh in data.get("Meshes"):
                if not any(meshes, lambda override_mesh: override_mesh.get("Type") == mesh.get("Type")):
                    meshes.append(mesh)

        self.meshes = meshes
        for mesh in meshes:
            self.import_model(mesh, collection=self.collection)

        if self.type == "Outfit" and self.options.get("MergeSkeletons"):
            master_skeleton = merge_skeletons(self.imported_meshes)
            master_mesh = get_armature_mesh(master_skeleton)
            if self.options.get("MeshDeformFixes"):
                master_mesh.modifiers[0].use_deform_preserve_volume = True #armature modifier
                corrective_smooth = master_mesh.modifiers.new(name="Corrective Smooth", type='CORRECTIVE_SMOOTH')
                corrective_smooth.use_pin_boundary = True
                
            for crunch_verts_material in self.crunch_verts_materials:
                geo_nodes = master_mesh.modifiers.new("Crunch Verts", "NODES")
                geo_nodes.node_group = bpy.data.node_groups.get("FP Crunch Verts")
                geo_nodes["Socket_3"] = crunch_verts_material

            if self.is_toon:
                # todo custom outline color from mat
                master_mesh.data.materials.append(bpy.data.materials.get("M_FP_Outline"))

                solidify = master_mesh.modifiers.new(name="Outline", type='SOLIDIFY')
                solidify.thickness = 0.001
                solidify.offset = 1
                solidify.thickness_clamp = 5.0
                solidify.use_rim = False
                solidify.use_flip_normals = True
                solidify.material_offset = len(master_mesh.data.materials) - 1

            if self.rig_type == ERigType.TASTY:
                apply_tasty_rig(master_skeleton, 1 if self.options.get("ScaleDown") else 100, self.options.get("UseFingerIK"))


    def import_anim_data(self, data, override_skeleton=None):
        name = data.get("Name")

        target_skeleton = override_skeleton or armature_from_selection()
        if target_skeleton is None:
            MessageServer.instance.send("An armature must be selected to import an animation. Please select an armature and try again.")
            return
        
        if target_skeleton.get("is_tasty_rig"):
            MessageServer.instance.send("Tasty Rig currently does not support emotes. Please use a character with the Default Rig and try again.")
            return

        # clear old data
        target_skeleton.animation_data_clear()
        if bpy.context.scene.sequence_editor:
            sequences_to_remove = where(bpy.context.scene.sequence_editor.sequences, lambda seq: seq["FPSound"])
            for sequence in sequences_to_remove:
                bpy.context.scene.sequence_editor.sequences.remove(sequence)

        # start import
        target_skeleton.animation_data_create()
        target_track = target_skeleton.animation_data.nla_tracks.new(prev=None)
        target_track.name = "Sections"

        def import_sections(sections, skeleton, track):
            total_frames = 0
            for section in sections:
                path = section.get("Path")
    
                total_frames += time_to_frame(section.get("Length"))
    
                anim = self.import_anim(path, skeleton)
                track.strips.new(section.get("Name"), time_to_frame(section.get("Time")), anim)
            return total_frames
        
        total_frames = import_sections(data.get("Sections"), target_skeleton, target_track)
        if self.options.get("UpdateTimelineLength"):
            bpy.context.scene.frame_end = total_frames
            
        props = data.get("Props")
        if len(props) > 0:
            if master_skeleton := first(target_skeleton.children, lambda child: child.name == "Master_Skeleton"):
                bpy.data.objects.remove(master_skeleton)
                
            master_skeleton = self.import_model(data.get("Skeleton"))
            master_skeleton.name = "Master_Skeleton"
            master_skeleton.parent = target_skeleton
            master_skeleton.animation_data_create()

            master_track = master_skeleton.animation_data.nla_tracks.new(prev=None)
            master_track.name = "Sections"

            import_sections(data.get("Sections"), master_skeleton, master_track)
            
            for prop in props:
                mesh = self.import_model(prop.get("Mesh"))
                mesh.rotation_euler = make_euler(prop.get("RotationOffset"))
                mesh.location = make_vector(prop.get("LocationOffset"), mirror_y=True) * 0.01
                mesh.scale = make_vector(prop.get("Scale"))
                constraint_object(mesh, master_skeleton, prop.get("SocketName"), [0, 0, 0])

                if (anims := prop.get("AnimSections")) and len(anims) > 0:
                    mesh.animation_data_create()
                    mesh_track = mesh.animation_data.nla_tracks.new(prev=None)
                    mesh_track.name = "Sections"
                    import_sections(anims, mesh, mesh_track)

            master_skeleton.hide_set(True)
            
        if self.options.get("ImportSounds"):
            for sound in data.get("Sounds"):
                path = sound.get("Path")
                self.import_sound(path, time_to_frame(sound.get("Time")))
                
                
    def import_texture_data(self, data):
        import_type = ETextureExportTypes(self.options.get("TextureExportType"))
        path = data.get("Path")
        
        match import_type:
            case ETextureExportTypes.DATA:
                self.import_image(path)
            case ETextureExportTypes.PLANE:
                if "io_import_images_as_planes" not in bpy.context.preferences.addons:
                    bpy.ops.preferences.addon_enable(module='io_import_images_as_planes')

                path, name = self.format_image_path(path)
                bpy.ops.import_image.to_plane(shader="EMISSION", files=[{"name": path}])
        

    def import_model(self, mesh, collection=None, parent=None):
        mesh_type = mesh.get("Type")
        mesh_path = mesh.get("Path")
        mesh_name = mesh_path.split(".")[1]
        object_name = mesh.get("Name")

        if collection is None:
            collection = bpy.context.scene.collection

        if self.type in ["World", "Prefab"] and (existing_mesh_data := bpy.data.meshes.get(mesh_name)):
            imported_object = bpy.data.objects.new(object_name, existing_mesh_data)
            collection.objects.link(imported_object)
        else:
            imported_object = self.import_mesh(mesh.get("Path"), mesh.get("NumLods"))
            imported_object.name = object_name

        if self.type in ["World", "Prefab"]:
            self.imported_mesh_count += 1
            Log.info(f"Actor {self.imported_mesh_count}/{len(self.meshes)}: {object_name}")

        if parent:
            imported_object.parent = parent

        imported_object.rotation_euler = make_euler(mesh.get("Rotation"))
        imported_object.location = make_vector(mesh.get("Location"), mirror_y=True) * 0.01
        imported_object.scale = make_vector(mesh.get("Scale"))
        imported_mesh = get_armature_mesh(imported_object)
        self.imported_meshes.append({
            "Skeleton": imported_object,
            "Mesh": imported_mesh,
            "Data": mesh,
            "Meta": mesh.get("Meta")
        })

        def get_meta(search_props):
            out_props = {}
            for mesh in self.meshes:
                meta = mesh.get("Meta")
                for search_prop in search_props:
                    if found_key := first(meta.keys(), lambda key: key == search_prop):
                        out_props[found_key] = meta.get(found_key)
            return out_props

        # fetch metadata
        match mesh_type:
            case "Body":
                meta = get_meta(["SkinColor"])
            case "Head":
                meta = get_meta(["MorphNames", "HatType", "PoseData"])

                shape_keys = imported_mesh.data.shape_keys
                if (morph_name := meta.get("MorphNames").get(meta.get("HatType"))) and shape_keys is not None:
                    for key in shape_keys.key_blocks:
                        if key.name.casefold() == morph_name.casefold():
                            key.value = 1.0
            case _:
                meta = {}

        if self.options.get("UseQuads"):
            bpy.context.view_layer.objects.active = imported_mesh
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.tris_convert_to_quads(uvs=True)
            bpy.ops.object.mode_set(mode='OBJECT')

        meta["TextureData"] = mesh.get("TextureData")
        meta["OverrideParameters"] = self.override_parameters

        # import mats
        for material in mesh.get("Materials"):
            index = material.get("Slot")
            if index >= len(imported_mesh.material_slots):
                continue

            self.import_material(imported_mesh.material_slots[index], material, meta)
            
            material_name = material.get("Name")
            if any(["Outline", "Toon_Lines"], lambda x: x in material_name):
                bm = bmesh.new()
                bm.from_mesh(imported_mesh.data)
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == index], context='FACES')
                bm.to_mesh(imported_mesh.data)
                bm.free()

        for override_material in mesh.get("OverrideMaterials"):
            index = override_material.get("Slot")
            if index >= len(imported_mesh.material_slots):
                continue

            overridden_material = imported_mesh.material_slots[index]
            slots = where(imported_mesh.material_slots,
                          lambda slot: slot.name.casefold() == overridden_material.name.casefold())
            for slot in slots:
                self.import_material(slot, override_material, meta)

        for variant_override_material in self.override_materials:
            material_name_to_swap = variant_override_material.get("MaterialNameToSwap")
            slots = where(imported_mesh.material_slots,
                          lambda slot: slot.name.casefold() == material_name_to_swap.casefold())
            for slot in slots:
                self.import_material(slot, variant_override_material, meta)
                
        for slot in imported_mesh.material_slots:
            if not slot.material.get("Crunch Verts"):
                continue

            add_unique(self.crunch_verts_materials, slot.material)

        for child in mesh.get("Children"):
            self.import_model(child, collection, imported_object)
            
        return imported_object
            
    def import_material(self, material_slot, material_data, meta_data):
        temp_material = material_slot.material
        material_slot.link = 'OBJECT'
        material_slot.material = temp_material
        
        material_name = material_data.get("Name")
        material_hash = material_data.get("Hash")
        additional_hash = 0

        texture_data = meta_data.get("TextureData")
        if texture_data:
            for data in texture_data:
                additional_hash += data.get("Hash")

        override_parameters = where(meta_data.get("OverrideParameters"),
                                    lambda param: param.get("MaterialNameToAlter") == material_name)
        if override_parameters:
            for parameters in override_parameters:
                additional_hash += parameters.get("Hash")

        if additional_hash != 0:
            material_name += f"_{hash_code(additional_hash)}"
            material_hash += additional_hash

        if existing := self.imported_materials.get(material_hash):
            material_slot.material = existing
            return

        if material_slot.material.name.casefold() != material_name.casefold():
            material_slot.material = bpy.data.materials.new(material_name)

        self.imported_materials[material_hash] = material_slot.material
        material = material_slot.material
        material.use_nodes = True
        material.blend_method = "CLIP"
        material.shadow_method = "CLIP"
        nodes = material.node_tree.nodes
        nodes.clear()
        links = material.node_tree.links
        links.clear()

        textures = material_data.get("Textures")
        scalars = material_data.get("Scalars")
        vectors = material_data.get("Vectors")
        switches = material_data.get("Switches")
        component_masks = material_data.get("ComponentMasks")

        if texture_data:
            for texture_data_inst in texture_data:
                replace_or_add_parameter(textures, texture_data_inst.get("Diffuse"))
                replace_or_add_parameter(textures, texture_data_inst.get("Normal"))
                replace_or_add_parameter(textures, texture_data_inst.get("Specular"))

        if override_parameters:
            for override_parameter in override_parameters:
                for texture in override_parameter.get("Textures"):
                    replace_or_add_parameter(textures, texture)

                for scalar in override_parameter.get("Scalars"):
                    replace_or_add_parameter(scalars, scalar)

                for vector in override_parameter.get("Vectors"):
                    replace_or_add_parameter(vectors, vector)

        output_node = nodes.new(type="ShaderNodeOutputMaterial")
        output_node.location = (200, 0)

        shader_node = nodes.new(type="ShaderNodeGroup")
        shader_node.node_tree = bpy.data.node_groups.get("FP Material")

        def replace_shader_node(name):
            nonlocal shader_node
            nodes.remove(shader_node)
            shader_node = nodes.new(type="ShaderNodeGroup")
            shader_node.node_tree = bpy.data.node_groups.get(name)


        # parameters
        unused_parameter_offset = 0
        socket_mappings = default_mappings

        def get_param(source, name):
            found = first(source, lambda param: param.get("Name") == name)
            if found is None:
                return None
            return found.get("Value")

        def get_param_multiple(source, names):
            found = first(source, lambda param: param.get("Name") in names)
            if found is None:
                return None
            return found.get("Value")

        def texture_param(data, target_mappings, target_node = shader_node, add_unused_params = False):
            try:
                name = data.get("Name")
                path = data.get("Value")

                node = nodes.new(type="ShaderNodeTexImage")
                node.image = self.import_image(path)
                node.image.alpha_mode = 'CHANNEL_PACKED'
                node.image.colorspace_settings.name = "sRGB" if data.get("sRGB") else "Non-Color"
                node.interpolation = "Smart"
                node.hide = True

                mappings = first(target_mappings.textures, lambda x: x.name == name)
                if mappings is None:
                    if add_unused_params:
                        nonlocal unused_parameter_offset
                        node.label = name
                        node.location = 400, unused_parameter_offset
                        unused_parameter_offset -= 50
                    return

                x, y = get_socket_pos(target_node, target_node.inputs.find(mappings.slot))
                node.location = x - 300, y
                links.new(node.outputs[0], target_node.inputs[mappings.slot])

                if mappings.alpha_slot:
                    links.new(node.outputs[1], target_node.inputs[mappings.alpha_slot])
                if mappings.switch_slot:
                    target_node.inputs[mappings.switch_slot].default_value = 1 if value else 0
                if mappings.coords != "UV0":
                    uv = nodes.new(type="ShaderNodeUVMap")
                    uv.location = node.location.x - 250, node.location.y
                    uv.uv_map = mappings.coords
                    links.new(uv.outputs[0], node.inputs[0])
            except Exception as e:
                traceback.print_exc()

        def scalar_param(data, target_mappings, target_node = shader_node, add_unused_params = False):
            try:
                name = data.get("Name")
                value = data.get("Value")
                
                mappings = first(target_mappings.scalars, lambda x: x.name == name)
                if mappings is None:
                    if add_unused_params:
                        nonlocal unused_parameter_offset
                        node = nodes.new(type="ShaderNodeValue")
                        node.outputs[0].default_value = value
                        node.label = name
                        node.width = 250
                        node.location = 400, unused_parameter_offset
                        unused_parameter_offset -= 100
                    return

                value = mappings.value_func(value) if mappings.value_func else value
                target_node.inputs[mappings.slot].default_value = value
                if mappings.switch_slot:
                    target_node.inputs[mappings.switch_slot].default_value = 1 if value else 0
            except Exception as e:
                traceback.print_exc()

        def vector_param(data, target_mappings, target_node = shader_node, add_unused_params = False):
            try:
                name = data.get("Name")
                value = data.get("Value")

                mappings = first(target_mappings.vectors, lambda x: x.name == name)
                if mappings is None:
                    if add_unused_params:
                        nonlocal unused_parameter_offset
                        node = nodes.new(type="ShaderNodeRGB")
                        node.outputs[0].default_value = (value["R"], value["G"], value["B"], value["A"])
                        node.label = name
                        node.width = 250
                        node.location = 400, unused_parameter_offset
                        unused_parameter_offset -= 200
                    return

                value = mappings.value_func(value) if mappings.value_func else value
                target_node.inputs[mappings.slot].default_value = (value["R"], value["G"], value["B"], 1.0)
                if mappings.alpha_slot:
                    target_node.inputs[mappings.alpha_slot].default_value = value["A"]
                if mappings.switch_slot:
                    target_node.inputs[mappings.switch_slot].default_value = 1 if value else 0
            except Exception as e:
                traceback.print_exc()

        def component_mask_param(data, target_mappings, target_node = shader_node, add_unused_params = False):
            try:
                name = data.get("Name")
                value = data.get("Value")
                
                mappings = first(target_mappings.component_masks, lambda x: x.name == name)
                if mappings is None:
                    if add_unused_params:
                        nonlocal unused_parameter_offset
                        node = nodes.new(type="ShaderNodeRGB")
                        node.outputs[0].default_value = (value["R"], value["G"], value["B"], value["A"])
                        node.label = name
                        node.width = 250
                        node.location = 400, unused_parameter_offset
                        unused_parameter_offset -= 200
                    return

                value = mappings.value_func(value) if mappings.value_func else value
                target_node.inputs[mappings.slot].default_value = (value["R"], value["G"], value["B"], value["A"])
            except Exception as e:
                traceback.print_exc()

        def switch_param(data, target_mappings, target_node = shader_node, add_unused_params = False):
            try:
                name = data.get("Name")
                value = data.get("Value")

                mappings = first(target_mappings.switches, lambda x: x.name == name)
                if mappings is None:
                    if add_unused_params:
                        nonlocal unused_parameter_offset
                        node = nodes.new("ShaderNodeGroup")
                        node.node_tree = bpy.data.node_groups.get("FP Switch")
                        node.inputs[0].default_value = 1 if value else 0
                        node.label = name
                        node.width = 250
                        node.location = 400, unused_parameter_offset
                        unused_parameter_offset -= 125
                    return


                value = mappings.value_func(value) if mappings.value_func else value
                target_node.inputs[mappings.slot].default_value = 1 if value else 0
            except Exception as e:
                traceback.print_exc()
                
        layer_switch_names = ["Use 2 Layers", "Use 3 Layers", "Use 4 Layers", "Use 5 Layers", "Use 6 Layers", "Use 7 Layers",
            "Use 2 Materials", "Use 3 Materials", "Use 4 Materials", "Use 5 Materials", "Use 6 Materials", "Use 7 Materials",
            "Use_Multiple_Material_Textures"]
        extra_layer_names = ["Diffuse_Texture_2", "SpecularMasks_2", "Normals_Texture_2", "Emissive_Texture_2", 
                             "Diffuse_Texture_3", "SpecularMasks_3", "Normals_Texture_3", "Emissive_Texture_3", 
                             "Diffuse_Texture_4", "SpecularMasks_4", "Normals_Texture_4", "Emissive_Texture_4", 
                             "Diffuse_Texture_5", "SpecularMasks_5", "Normals_Texture_5", "Emissive_Texture_5", 
                             "Diffuse_Texture_6", "SpecularMasks_6", "Normals_Texture_6", "Emissive_Texture_6",]
        if get_param_multiple(switches, layer_switch_names) and get_param_multiple(textures, extra_layer_names):
            replace_shader_node("FP Layer")
            socket_mappings = layer_mappings

        if any(["LitDiffuse", "ShadedDiffuse"], lambda x: get_param(textures, x)):
            replace_shader_node("FP Toon")
            socket_mappings = toon_mappings

        if material_data.get("AbsoluteParent") == "M_FN_Valet_Master":
            replace_shader_node("FP Valet")
            socket_mappings = valet_mappings
            
        if material_data.get("UseGlassMaterial"):
            replace_shader_node("FP Glass")
            socket_mappings = glass_mappings
            material.blend_method = "BLEND"
            material.show_transparent_back = False

        is_trunk = get_param(switches, "IsTrunk")
        if is_trunk:
            socket_mappings = trunk_mappings

        if material_data.get("UseFoliageMaterial") and not is_trunk:
            replace_shader_node("FP Foliage")
            socket_mappings = foliage_mappings
            material.use_sss_translucency = True
            
        def setup_params(mappings, target_node, add_unused_params = False):
            for texture in textures:
                texture_param(texture, mappings, target_node, add_unused_params)
    
            for scalar in scalars:
                scalar_param(scalar, mappings, target_node, add_unused_params)
    
            for vector in vectors:
                vector_param(vector, mappings, target_node, add_unused_params)
    
            for component_mask in component_masks:
                component_mask_param(component_mask, mappings, target_node, add_unused_params)
    
            for switch in switches:
                switch_param(switch, mappings, target_node, add_unused_params)

        setup_params(socket_mappings, shader_node, True)

        links.new(shader_node.outputs[0], output_node.inputs[0])

        if material_name in ["MI_VertexCrunch", "M_VertexCrunch"] or get_param(scalars, "HT_CrunchVerts") == 1:
            material_slot.material["Crunch Verts"] = True
            shader_node.inputs["Alpha"].default_value = 0.0
            return

        if shader_node.node_tree.name == "FP Material":

            shader_node.inputs["AO"].default_value = self.options.get("AmbientOcclusion")
            shader_node.inputs["Cavity"].default_value = self.options.get("Cavity")
            shader_node.inputs["Subsurface"].default_value = self.options.get("Subsurface")

            # find better detection to do this
            '''if (diffuse_links := shader_node.inputs["Diffuse"].links) and len(diffuse_links) > 0:
				diffuse_node = diffuse_links[0].from_node
				links.new(diffuse_node.outputs[1], shader_node.inputs["Alpha"])'''

            if (skin_color := meta_data.get("SkinColor")) and skin_color["A"] != 0:
                shader_node.inputs["Skin Color"].default_value = (skin_color["R"], skin_color["G"], skin_color["B"], 1.0)
                shader_node.inputs["Skin Boost"].default_value = skin_color["A"]

            emissive_toggle_names = [
                "Emissive",
                "UseBasicEmissive",
                "UseAdvancedEmissive",
                "Use Emissive"
            ]
            if get_param_multiple(switches, emissive_toggle_names) is False:
                shader_node.inputs["Emission Strength"].default_value = 0

            if get_param(textures, "SRM"):
                shader_node.inputs["SwizzleRoughnessToGreen"].default_value = 1

            if get_param(switches, "Use Vertex Colors for Mask"):
                color_node = nodes.new(type="ShaderNodeVertexColor")
                color_node.location = [-400, -560]
                color_node.layer_name = "COL0"

                mask_node = nodes.new("ShaderNodeGroup")
                mask_node.node_tree = bpy.data.node_groups.get("FP Vertex Alpha")
                mask_node.location = [-200, -560]

                links.new(color_node.outputs[0], mask_node.inputs[0])
                links.new(mask_node.outputs[0], shader_node.inputs["Alpha"])

                for scalar in scalars:
                    name = scalar.get("Name")
                    value = scalar.get("Value")
                    if not "Hide Element" in scalar:
                        continue
                        
                    if input := mask_node.inputs.get(name.replace("Hide ", "")):
                        input.default_value = int(value)

            emission_slot = shader_node.inputs["Emission"]
            emission_crop_vector_params = [
                "EmissiveUVs_RG_UpperLeftCorner_BA_LowerRightCorner",
                "Emissive Texture UVs RG_TopLeft BA_BottomRight",
                "Emissive 2 UV Positioning (RG)UpperLeft (BA)LowerRight",
                "EmissiveUVPositioning (RG)UpperLeft (BA)LowerRight"
            ]
            
            emission_crop_switch_params = [
                "CroppedEmissive",
                "Manipulate Emissive Uvs"
            ]
            
            if (crop_bounds := get_param_multiple(vectors, emission_crop_vector_params)) and get_param_multiple(switches, emission_crop_switch_params) and len(emission_slot.links) > 0:
                emission_node = emission_slot.links[0].from_node

                crop_texture_node = nodes.new("ShaderNodeGroup")
                crop_texture_node.node_tree = bpy.data.node_groups.get("FP Texture Cropping")
                crop_texture_node.location = emission_node.location + Vector((-200, 25))
                crop_texture_node.inputs["Left"].default_value = crop_bounds.get('R')
                crop_texture_node.inputs["Top"].default_value = crop_bounds.get('G')
                crop_texture_node.inputs["Right"].default_value = crop_bounds.get('B')
                crop_texture_node.inputs["Bottom"].default_value = crop_bounds.get('A')
                links.new(crop_texture_node.outputs[0], emission_node.inputs[0])


            if get_param(switches, "Modulate Emissive with Diffuse"):
                diffuse_node = shader_node.inputs["Diffuse"].links[0].from_node
                links.new(diffuse_node.outputs[0], shader_node.inputs["Emission Multiplier"])
                
            if get_param(switches, "useGmapGradientLayers"):
                gradient_node = nodes.new(type="ShaderNodeGroup")
                gradient_node.node_tree = bpy.data.node_groups.get("FP Gradient")
                gradient_node.location = -500, 0
                nodes.remove(shader_node.inputs["Diffuse"].links[0].from_node)
                links.new(gradient_node.outputs[0], shader_node.inputs[0])
                
                gmap_node = nodes.new("ShaderNodeValue")
                gmap_node.location = -1000, -120
                gmap_node.outputs[0].default_value = 1
                
                setup_params(gradient_mappings, gradient_node)
                
                for item in gradient_node.node_tree.interface.items_tree:
                    if item.name != "Colors":
                        continue
                        
                    panel_items = item.interface_items
                    for panel_item in panel_items:
                        item_links = gradient_node.inputs[panel_item.name].links
                        if len(item_links) == 0:
                            continue
                        links.new(gmap_node.outputs[0], item_links[0].from_node.inputs[0])
                        
                    
                

        if shader_node.node_tree.name == "FP Toon":
            shader_node.inputs["Brightness"].default_value = self.options.get("ToonBrightness")
            self.is_toon = True
            
            
    def format_image_path(self, path: str):
        path, name = path.split(".")
        path = path[1:] if path.startswith("/") else path
        ext = "png"
        texture_path = os.path.join(self.assets_folder, path + "." + ext)
        return texture_path, name

    def import_image(self, path: str):
        path, name = self.format_image_path(path)
        if existing := bpy.data.images.get(name):
            return existing

        if not os.path.exists(path):
            return None

        return bpy.data.images.load(path, check_existing=True)

    def import_mesh(self, path: str, num_lods):
        options = UEModelOptions(scale_factor=0.01 if self.options.get("ScaleDown") else 1,
                                 reorient_bones=self.options.get("ReorientBones"),
                                 bone_length=self.options.get("BoneSize"))

        path = path[1:] if path.startswith("/") else path
        
        lod_mesh_path = os.path.join(self.assets_folder, path.split(".")[0] + f"_LOD{str(min(num_lods - 1, self.options.get('LevelOfDetail')))}" + ".uemodel")
        normal_mesh_path = os.path.join(self.assets_folder, path.split(".")[0] + ".uemodel")
        mesh_path = lod_mesh_path if os.path.exists(lod_mesh_path) else normal_mesh_path
        
        return UEFormatImport(options).import_file(mesh_path)

    def import_anim(self, path: str, override_skeleton=None):
        path = path[1:] if path.startswith("/") else path
        file_path, name = path.split(".")
        if (existing := bpy.data.actions.get(name)) and existing["Skeleton"] == override_skeleton.name:
            return existing

        anim_path = os.path.join(self.assets_folder, file_path + ".ueanim")
        options = UEAnimOptions(link=False,
                                override_skeleton=override_skeleton,
                                scale_factor=0.01 if self.options.get("ScaleDown") else 1)
        anim = UEFormatImport(options).import_file(anim_path)
        anim["Skeleton"] = override_skeleton.name
        return anim

    def import_sound(self, path: str, time):
        path = path[1:] if path.startswith("/") else path
        file_path, name = path.split(".")
        if existing := bpy.data.sounds.get(name):
            return existing
        
        if not bpy.context.scene.sequence_editor:
            bpy.context.scene.sequence_editor_create()

        sound_path = os.path.join(self.assets_folder, file_path + ".wav")
        sound = bpy.context.scene.sequence_editor.sequences.new_sound(name, sound_path, 0, time)
        sound["FPSound"] = True
        return sound


def get_socket_pos(node, index):
    start_y = -80
    offset_y = -22
    return node.location.x, node.location.y + start_y + offset_y * index


def hash_code(num):
    return hex(abs(num))[2:]


def get_armature_mesh(obj):
    if obj.type == 'ARMATURE' and len(obj.children) > 0:
        return obj.children[0]

    if obj.type == 'MESH':
        return obj

def armature_from_selection():
    armature_obj = None

    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj.select_get():
            armature_obj = obj
            break

    if armature_obj is None:
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.select_get():
                for modifier in obj.modifiers:
                    if modifier.type == 'ARMATURE':
                        armature_obj = modifier.object
                        break

    return armature_obj

def time_to_frame(time, fps = 30):
    return int(round(time * fps))

def append_data():
    addon_dir = os.path.dirname(os.path.splitext(__file__)[0])
    with bpy.data.libraries.load(os.path.join(addon_dir, "fortnite_porting_data.blend")) as (data_from, data_to):
        for node_group in data_from.node_groups:
            if not bpy.data.node_groups.get(node_group):
                data_to.node_groups.append(node_group)

        for mat in data_from.materials:
            if not bpy.data.materials.get(mat):
                data_to.materials.append(mat)

        for obj in data_from.objects:
            if not bpy.data.objects.get(obj):
                data_to.objects.append(obj)


def create_collection(name):
    if name in bpy.context.view_layer.layer_collection.children:
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children.get(name)
        return
    bpy.ops.object.select_all(action='DESELECT')

    new_collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(new_collection)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children.get(
        new_collection.name)
    return new_collection


def constraint_object(child: bpy.types.Object, parent: bpy.types.Object, bone: str, rot=[0, radians(90), 0]):
    constraint = child.constraints.new('CHILD_OF')
    constraint.target = parent
    constraint.subtarget = bone
    child.rotation_mode = 'XYZ'
    child.rotation_euler = rot
    constraint.inverse_matrix = Matrix()


def make_vector(data, mirror_y=False):
    return Vector((data.get("X"), data.get("Y") * (-1 if mirror_y else 1), data.get("Z")))


def make_quat(data):
    return Quaternion((data.get("W"), data.get("X"), data.get("Y"), data.get("Z")))


def make_euler(data):
    return Euler((radians(data.get("Roll")), -radians(data.get("Pitch")), -radians(data.get("Yaw"))))


def first(target, expr, default=None):
    if not target:
        return None
    filtered = filter(expr, target)

    return next(filtered, default)


def where(target, expr):
    if not target:
        return []
    filtered = filter(expr, target)

    return list(filtered)


def any(target, expr):
    if not target:
        return False

    filtered = list(filter(expr, target))
    return len(filtered) > 0

def add_unique(target, item):
    if item in target:
        return
    
    target.append(item)


def get_case_insensitive(source, string):
    for item in source:
        if item.name.casefold() == string.casefold():
            return item


def replace_or_add_parameter(list, replace_item):
    if replace_item is None:
        return
    for index, item in enumerate(list):
        if item is None:
            continue

        if item.get("Name") == replace_item.get("Name"):
            list[index] = replace_item

    if not any(list, lambda x: x.get("Name") == replace_item.get("Name")):
        list.append(replace_item)


def merge_skeletons(parts):
    bpy.ops.object.select_all(action='DESELECT')

    merge_parts = []
    constraint_parts = []

    for part in parts:
        if (meta := part.get("Meta")) and meta.get("AttachToSocket") and meta.get("Socket") not in ["Face", "Helmet", None]:
            constraint_parts.append(part)
        else:
            merge_parts.append(part)

    # merge skeletons
    for part in merge_parts:
        data = part.get("Data")
        mesh_type = data.get("Type")
        skeleton = part.get("Skeleton")

        if mesh_type == "Body":
            bpy.context.view_layer.objects.active = skeleton

        skeleton.select_set(True)

    bpy.ops.object.join()
    master_skeleton = bpy.context.active_object
    master_mesh = get_armature_mesh(bpy.context.active_object)
    bpy.ops.object.select_all(action='DESELECT')

    # merge meshes
    for part in merge_parts:
        data = part.get("Data")
        mesh_type = data.get("Type")
        mesh = part.get("Mesh")

        if mesh_type == "Body":
            bpy.context.view_layer.objects.active = mesh

        mesh.select_set(True)

    bpy.ops.object.join()
    bpy.ops.object.select_all(action='DESELECT')

    # rebuild master bone tree
    bone_tree = {}
    for bone in master_skeleton.data.bones:
        try:
            bone_reg = re.sub(".\d\d\d", "", bone.name)
            parent_reg = re.sub(".\d\d\d", "", bone.parent.name)
            bone_tree[bone_reg] = parent_reg
        except AttributeError:
            pass

    bpy.context.view_layer.objects.active = master_skeleton
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.armature.select_all(action='DESELECT')
    bpy.ops.object.select_pattern(pattern="*.[0-9][0-9][0-9]")
    bpy.ops.armature.delete()

    skeleton_bones = master_skeleton.data.edit_bones

    for bone, parent in bone_tree.items():
        if target_bone := skeleton_bones.get(bone):
            target_bone.parent = skeleton_bones.get(parent)

    bpy.ops.object.mode_set(mode='OBJECT')

    # constraint meshes
    for part in constraint_parts:
        skeleton = part.get("Skeleton")
        meta = part.get("Meta")
        socket = meta.get("Socket")
        if socket is None:
            return

        if socket.casefold() == "hat":
            socket = "head"

        constraint_object(skeleton, master_skeleton, socket)

    return master_skeleton

class LazyInit:
    
    def __init__(self, gen):
        self.gen = gen

    def load(self):
        try:
            self.data = self.gen()
            return True
        except Exception:
            return False

    def get(self):
        return self.data


def apply_tasty_rig(master_skeleton, scale, use_finger_ik = True):
    master_skeleton["is_tasty_rig"] = True
    armature_data = master_skeleton.data
    armature_data["Use Finger IK"] = use_finger_ik

    main_collection = armature_data.collections.new("Main Bones")
    ik_collection = armature_data.collections.new("IK Bones")
    deform_collection = armature_data.collections.new("Deform Bones")
    dyn_collection = armature_data.collections.new("Dynamic Bones")
    face_collection = armature_data.collections.new("Face Bones")
    extra_collection = armature_data.collections.new("Extra Bones")


    bpy.ops.object.mode_set(mode='EDIT')

    edit_bones = armature_data.edit_bones

    new_bones = [
        ("tasty_root", "root", LazyInit(lambda: (edit_bones["root"].head, edit_bones["root"].tail, edit_bones["root"].roll))),
        
        ("ik_foot_parent_r", "tasty_root", LazyInit(lambda: (edit_bones["foot_r"].head, edit_bones["foot_r"].tail, edit_bones["foot_r"].roll))),
        ("ik_foot_ctrl_r", "ik_foot_parent_r", LazyInit(lambda: (edit_bones["ball_r"].head + Vector((0, 0.2, 0)), edit_bones["ball_r"].tail + Vector((0, 0.2, 0)), 0))),
        ("ik_foot_roll_inner_r", "ik_foot_parent_r", LazyInit(lambda: (Vector((edit_bones["ball_r"].head.x + 0.04, edit_bones["ball_r"].head.y, 0)), Vector((edit_bones["ball_r"].tail.x + 0.04, edit_bones["ball_r"].tail.y, 0)), 0))),
        ("ik_foot_roll_outer_r", "ik_foot_roll_inner_r", LazyInit(lambda: (Vector((edit_bones["ball_r"].head.x - 0.04, edit_bones["ball_r"].head.y, 0)), Vector((edit_bones["ball_r"].tail.x - 0.04, edit_bones["ball_r"].tail.y, 0)), 0))),
        ("ik_foot_roll_front_r", "ik_foot_roll_outer_r", LazyInit(lambda: (edit_bones["ball_r"].head, edit_bones["ball_r"].tail, radians(180)))),
        ("ik_foot_roll_back_r", "ik_foot_roll_front_r", LazyInit(lambda: (Vector((edit_bones["foot_r"].head.x, edit_bones["foot_r"].head.y + 0.065, 0)), Vector((edit_bones["foot_r"].tail.x, edit_bones["foot_r"].tail.y + 0.065, 0)), 0))),
        ("ik_foot_target_r", "ik_foot_roll_back_r", LazyInit(lambda: (edit_bones["foot_r"].head, edit_bones["foot_r"].tail, edit_bones["foot_r"].roll))),
        ("ik_foot_pole_r", "tasty_root", LazyInit(lambda: (edit_bones["calf_r"].head + Vector((0, -0.75, 0)) * scale, edit_bones["calf_r"].tail + Vector((0, -0.80, 0)) * scale, 0))),
        
        ("ik_foot_parent_l", "tasty_root", LazyInit(lambda: (edit_bones["foot_l"].head, edit_bones["foot_l"].tail, edit_bones["foot_l"].roll))),
        ("ik_foot_ctrl_l", "ik_foot_parent_l", LazyInit(lambda: (edit_bones["ball_l"].head + Vector((0, 0.2, 0)), edit_bones["ball_l"].tail + Vector((0, 0.2, 0)), 0))),
        ("ik_foot_roll_inner_l", "ik_foot_parent_l", LazyInit(lambda: (Vector((edit_bones["ball_l"].head.x - 0.04, edit_bones["ball_l"].head.y, 0)), Vector((edit_bones["ball_l"].tail.x - 0.04, edit_bones["ball_l"].tail.y, 0)), 0))),
        ("ik_foot_roll_outer_l", "ik_foot_roll_inner_l", LazyInit(lambda: (Vector((edit_bones["ball_l"].head.x + 0.04, edit_bones["ball_l"].head.y, 0)), Vector((edit_bones["ball_l"].tail.x + 0.04, edit_bones["ball_l"].tail.y, 0)), 0))),
        ("ik_foot_roll_front_l", "ik_foot_roll_outer_l", LazyInit(lambda: (edit_bones["ball_l"].head, edit_bones["ball_l"].tail, radians(180)))),
        ("ik_foot_roll_back_l", "ik_foot_roll_front_l", LazyInit(lambda: (Vector((edit_bones["foot_l"].head.x, edit_bones["foot_l"].head.y + 0.065, 0)), Vector((edit_bones["foot_l"].tail.x, edit_bones["foot_l"].tail.y + 0.065, 0)), 0))),
        ("ik_foot_target_l", "ik_foot_roll_back_l", LazyInit(lambda: (edit_bones["foot_l"].head, edit_bones["foot_l"].tail, edit_bones["foot_l"].roll))),
        ("ik_foot_pole_l", "tasty_root", LazyInit(lambda: (edit_bones["calf_l"].head + Vector((0, -0.75, 0)) * scale, edit_bones["calf_l"].tail + Vector((0, -0.80, 0)) * scale, 0))),

        ("ik_hand_parent_r", "tasty_root", LazyInit(lambda: (edit_bones["hand_r"].head, edit_bones["hand_r"].tail, edit_bones["hand_r"].roll))),
        ("ik_hand_target_r", "ik_hand_parent_r", LazyInit(lambda: (edit_bones["hand_r"].head, edit_bones["hand_r"].tail, edit_bones["hand_r"].roll))),
        ("ik_finger_thumb_r", "ik_hand_parent_r", LazyInit(lambda: (edit_bones["thumb_03_r"].tail, 2 * edit_bones["thumb_03_r"].tail - edit_bones["thumb_03_r"].head, edit_bones["thumb_03_r"].roll))),
        ("ik_finger_index_r", "ik_hand_parent_r", LazyInit(lambda: (edit_bones["index_03_r"].tail, 2 * edit_bones["index_03_r"].tail - edit_bones["index_03_r"].head, edit_bones["index_03_r"].roll))),
        ("ik_finger_middle_r", "ik_hand_parent_r", LazyInit(lambda: (edit_bones["middle_03_r"].tail, 2 * edit_bones["middle_03_r"].tail - edit_bones["middle_03_r"].head, edit_bones["middle_03_r"].roll))),
        ("ik_finger_ring_r", "ik_hand_parent_r", LazyInit(lambda: (edit_bones["ring_03_r"].tail, 2 * edit_bones["ring_03_r"].tail - edit_bones["ring_03_r"].head, edit_bones["ring_03_r"].roll))),
        ("ik_finger_pinky_r", "ik_hand_parent_r", LazyInit(lambda: (edit_bones["pinky_03_r"].tail, 2 * edit_bones["pinky_03_r"].tail - edit_bones["pinky_03_r"].head, edit_bones["pinky_03_r"].roll))),
        ("ik_hand_pole_r", "tasty_root", LazyInit(lambda: (edit_bones["lowerarm_r"].head + Vector((0, 0.75, 0)) * scale, edit_bones["lowerarm_r"].tail + Vector((0, 0.80, 0)) * scale, 0))),
        
        ("ik_hand_parent_l", "tasty_root", LazyInit(lambda: (edit_bones["hand_l"].head, edit_bones["hand_l"].tail, edit_bones["hand_l"].roll))),
        ("ik_hand_target_l", "ik_hand_parent_l", LazyInit(lambda: (edit_bones["hand_l"].head, edit_bones["hand_l"].tail, edit_bones["hand_l"].roll))),
        ("ik_finger_thumb_l", "ik_hand_parent_l", LazyInit(lambda: (edit_bones["thumb_03_l"].tail, 2 * edit_bones["thumb_03_l"].tail - edit_bones["thumb_03_l"].head, edit_bones["thumb_03_l"].roll))),
        ("ik_finger_index_l", "ik_hand_parent_l", LazyInit(lambda: (edit_bones["index_03_l"].tail, 2 * edit_bones["index_03_l"].tail - edit_bones["index_03_l"].head, edit_bones["index_03_l"].roll))),
        ("ik_finger_middle_l", "ik_hand_parent_l", LazyInit(lambda: (edit_bones["middle_03_l"].tail, 2 * edit_bones["middle_03_l"].tail - edit_bones["middle_03_l"].head, edit_bones["middle_03_l"].roll))),
        ("ik_finger_ring_l", "ik_hand_parent_l", LazyInit(lambda: (edit_bones["ring_03_l"].tail, 2 * edit_bones["ring_03_l"].tail - edit_bones["ring_03_l"].head, edit_bones["ring_03_l"].roll))),
        ("ik_finger_pinky_l", "ik_hand_parent_l", LazyInit(lambda: (edit_bones["pinky_03_l"].tail, 2 * edit_bones["pinky_03_l"].tail - edit_bones["pinky_03_l"].head, edit_bones["pinky_03_l"].roll))),
        ("ik_hand_pole_l", "tasty_root", LazyInit(lambda: (edit_bones["lowerarm_l"].head + Vector((0, 0.75, 0)) * scale, edit_bones["lowerarm_l"].tail + Vector((0, 0.80, 0)) * scale, 0))),

        ("ik_dog_ball_r", "ik_foot_target_r", LazyInit(lambda: (edit_bones["dog_ball_r"].tail, 2 * edit_bones["dog_ball_r"].tail - edit_bones["dog_ball_r"].head, edit_bones["dog_ball_r"].roll))),
        ("ik_dog_ball_l", "ik_foot_target_l", LazyInit(lambda: (edit_bones["dog_ball_l"].tail, 2 * edit_bones["dog_ball_l"].tail - edit_bones["dog_ball_l"].head, edit_bones["dog_ball_l"].roll))),

        ("ik_wolf_ball_r", "ik_foot_target_r", LazyInit(lambda: (edit_bones["wolf_ball_r"].tail, 2 * edit_bones["wolf_ball_r"].tail - edit_bones["wolf_ball_r"].head, edit_bones["wolf_ball_r"].roll))),
        ("ik_wolf_ball_l", "ik_foot_target_l", LazyInit(lambda: (edit_bones["wolf_ball_l"].tail, 2 * edit_bones["wolf_ball_l"].tail - edit_bones["wolf_ball_l"].head, edit_bones["wolf_ball_l"].roll))),

        ("eye_control_parent", "tasty_root", LazyInit(lambda: (edit_bones["head"].head + Vector((0, -0.675, 0)) * scale, edit_bones["head"].head + Vector((0, -0.7, 0)) * scale, 0))),
        ("eye_control_r", "eye_control_parent", LazyInit(lambda: (edit_bones["eye_control_parent"].head - Vector((0.0325, 0, 0)) * scale, edit_bones["eye_control_parent"].tail - Vector((0.0325, 0, 0)) * scale, 0))),
        ("eye_control_l", "eye_control_parent", LazyInit(lambda: (edit_bones["eye_control_parent"].head + Vector((0.0325, 0, 0)) * scale, edit_bones["eye_control_parent"].tail + Vector((0.0325, 0, 0)) * scale, 0)))
    ]

    for bone_name, parent_name, data in new_bones:
        if not data.load(): continue

        bone = edit_bones.get(bone_name) or edit_bones.new(bone_name)
        bone.parent = edit_bones.get(parent_name)

        head, tail, roll = data.get()
        bone.head = head
        bone.tail = tail
        bone.roll = roll
        
    parent_adjustment_bones = [
        ("L_eye_lid_lower_mid", "faceAttach"),
        ("L_eye_lid_upper_mid", "faceAttach"),
        ("R_eye_lid_lower_mid", "faceAttach"),
        ("R_eye_lid_upper_mid", "faceAttach")
    ]

    for name, parent in parent_adjustment_bones:
        if not (bone := edit_bones.get(name)): continue
        if not (parent_bone := edit_bones.get(parent)): continue

        bone.parent = parent_bone

    head_adjustment_bones = [
        ("calf_r", edit_bones["calf_r"].head + Vector((0.0075, 0, 0))),
        ("calf_l", edit_bones["calf_l"].head - Vector((0.0075, 0, 0))),
    ]

    for name, loc in head_adjustment_bones:
        if not (bone := edit_bones.get(name)): continue

        bone.head = loc
        
    tail_adjustment_bones = [
        ("calf_r", LazyInit(lambda: edit_bones["ik_foot_target_r"].head)),
        ("calf_l", LazyInit(lambda: edit_bones["ik_foot_target_l"].head)),
        ("lowerarm_r", LazyInit(lambda: edit_bones["ik_hand_target_r"].head)),
        ("lowerarm_l", LazyInit(lambda: edit_bones["ik_hand_target_l"].head)),
        ("R_eye", LazyInit(lambda: edit_bones["R_eye"].head - Vector((0, 0.1, 0)) * scale)),
        ("L_eye", LazyInit(lambda: edit_bones["L_eye"].head - Vector((0, 0.1, 0)) * scale)),
        ("FACIAL_R_Eye", LazyInit(lambda: edit_bones["FACIAL_R_Eye"].head - Vector((0, 0.1, 0)) * scale)),
        ("FACIAL_L_Eye", LazyInit(lambda: edit_bones["FACIAL_L_Eye"].head - Vector((0, 0.1, 0)) * scale)),
        ("C_jaw", LazyInit(lambda: edit_bones["C_jaw"].head + Vector((0, -0.1, 0)) * scale)),

        ("pelvis", LazyInit(lambda: edit_bones["pelvis"].head + Vector((0, 0, 0.15)) * scale)),
        ("spine_01", LazyInit(lambda: edit_bones["spine_01"].head + Vector((0, 0, edit_bones["spine_01"].length)) * scale)),
        ("spine_02", LazyInit(lambda: edit_bones["spine_02"].head + Vector((0, 0, edit_bones["spine_02"].length)) * scale)),
        ("spine_03", LazyInit(lambda: edit_bones["spine_03"].head + Vector((0, 0, edit_bones["spine_03"].length)) * scale)),
        ("spine_04", LazyInit(lambda: edit_bones["spine_04"].head + Vector((0, 0, edit_bones["spine_04"].length)) * scale)),
        ("spine_05", LazyInit(lambda: edit_bones["spine_05"].head + Vector((0, 0, edit_bones["spine_05"].length)) * scale)),
        ("neck_01", LazyInit(lambda: edit_bones["neck_01"].head + Vector((0, 0, edit_bones["neck_01"].length)) * scale)),
        ("neck_02", LazyInit(lambda: edit_bones["neck_02"].head + Vector((0, 0, edit_bones["neck_02"].length)) * scale)),
        ("head", LazyInit(lambda: edit_bones["head"].head + Vector((0, 0, edit_bones["head"].length)) * scale)),
    ]
    
    for name, data in tail_adjustment_bones:
        if not data.load(): continue
        if not (bone := edit_bones.get(name)): continue
        
        bone.tail = data.get()

    roll_adjustment_bones = [
        ("ball_r", 0),
        ("ball_l", 0),
        ("C_jaw", 0),
    ]

    for name, roll in roll_adjustment_bones:
        if not (bone := edit_bones.get(name)): continue

        bone.roll = roll

    if (lower_lip_bone := edit_bones.get("FACIAL_C_LowerLipRotation")) and (jaw_bone := edit_bones.get("FACIAL_C_Jaw")):
        lower_lip_bone.parent = jaw_bone
        
    bpy.ops.object.mode_set(mode='POSE')
    
    pose_bones = master_skeleton.pose.bones
    
    bone_shapes = [
        ("root", "RIG_Root", 0.75, Euler((radians(90), 0, 0))),
        ("pelvis", "RIG_Torso", 1.5, Euler((0, radians(-90), 0))),
        ("spine_01", "RIG_Hips", 2.2),
        ("spine_02", "RIG_Hips", 1.8),
        ("spine_03", "RIG_Hips", 1.6),
        ("spine_04", "RIG_Hips", 1.2),
        ("spine_05", "RIG_Hips", 1.6),
        ("neck_01", "RIG_Hips", 2.0),
        ("neck_02", "RIG_Hips", 1.4),
        ("head", "RIG_Hips", 2.6),

        ('clavicle_r', 'RIG_Shoulder', 1.0),
        ('clavicle_l', 'RIG_Shoulder', 1.0),

        ('upperarm_twist_01_r', 'RIG_Forearm', 0.13),
        ('upperarm_twist_02_r', 'RIG_Forearm', 0.10),
        ('lowerarm_twist_01_r', 'RIG_Forearm', 0.13),
        ('lowerarm_twist_02_r', 'RIG_Forearm', 0.13),
        ('upperarm_twist_01_l', 'RIG_Forearm', 0.13),
        ('upperarm_twist_02_l', 'RIG_Forearm', 0.10),
        ('lowerarm_twist_01_l', 'RIG_Forearm', 0.13),
        ('lowerarm_twist_02_l', 'RIG_Forearm', 0.13),

        ('thigh_twist_01_r', 'RIG_Tweak', 0.15),
        ('calf_twist_01_r', 'RIG_Tweak', 0.13),
        ('calf_twist_02_r', 'RIG_Tweak', 0.2),
        ('thigh_twist_01_l', 'RIG_Tweak', 0.15),
        ('calf_twist_01_l', 'RIG_Tweak', 0.13),
        ('calf_twist_02_l', 'RIG_Tweak', 0.2),

        ("ik_foot_parent_r", "RIG_FootR", 1.0),
        ("ik_foot_parent_l", "RIG_FootL", 1.0, Euler((0, radians(-90), 0))),
        ("ik_foot_pole_r", "RIG_Tweak", 0.75),
        ("ik_foot_pole_l", "RIG_Tweak", 0.75),
        ("ik_foot_ctrl_r", "RIG_Ctrl", 7.5, Euler((radians(90), 0, 0))),
        ("ik_foot_ctrl_l", "RIG_Ctrl", 7.5, Euler((radians(90), 0, 0))),

        ("ik_hand_parent_r", "RIG_Hand", 2.2),
        ("ik_hand_target_r", "RIG_Ctrl", 7.5, Euler((0, radians(-90), 0))),
        ("ik_hand_pole_r", "RIG_Tweak", 0.75),
        ("ik_finger_thumb_r", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),
        ("ik_finger_index_r", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),
        ("ik_finger_middle_r", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),
        ("ik_finger_ring_r", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),
        ("ik_finger_pinky_r", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),

        ("ik_hand_parent_l", "RIG_Hand", 2.2),
        ("ik_hand_target_l", "RIG_Ctrl", 7.5, Euler((0, radians(-90), 0))),
        ("ik_hand_pole_l", "RIG_Tweak", 0.75),
        ("ik_finger_thumb_l", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),
        ("ik_finger_index_l", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),
        ("ik_finger_middle_l", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),
        ("ik_finger_ring_l", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),
        ("ik_finger_pinky_l", "RIG_Finger", 1.0, Euler((0, 0, radians(180)))),
        
        ("eye_control_parent", "RIG_EyeTrackMid", 0.75, False),
        ("eye_control_r", "RIG_EyeTrackInd", 0.75, False),
        ("eye_control_l", "RIG_EyeTrackInd", 0.75, False),
        
        ("C_jaw", "RIG_JawBone", 0.1, False),
        ("FACIAL_C_Jaw", "RIG_JawBone", 0.1, False),
    ]
    
    for bone_name, shape_name, shape_scale, *extra in bone_shapes:
        if not (bone := pose_bones.get(bone_name)): continue
        if not (shape := bpy.data.objects.get(shape_name)): continue
        
        bone.custom_shape = shape
        bone.custom_shape_scale_xyz = (shape_scale, shape_scale, shape_scale) * scale
        
        if len(extra) > 0:
            if type(extra[0]) is Euler and (rot := extra[0]):
                bone.custom_shape_rotation_euler = rot
            else:
                bone.use_custom_shape_bone_size = extra[0]


    explicit_collection_bones = {
        "pelvis": main_collection,
        "spine_01": main_collection,
        "spine_02": main_collection,
        "spine_03": main_collection,
        "spine_04": main_collection,
        "spine_05": main_collection,
        "clavicle_r": main_collection,
        "clavicle_l": main_collection,
        "neck_01": main_collection,
        "neck_02": main_collection,
        "head": main_collection,
        "ik_foot_parent_r": ik_collection,
        "ik_foot_parent_l": ik_collection,
        "ik_foot_ctrl_r": ik_collection,
        "ik_foot_ctrl_l": ik_collection,
        "ik_foot_pole_r": ik_collection,
        "ik_foot_pole_l": ik_collection,

        "ik_hand_parent_r": ik_collection,
        "ik_hand_target_r": ik_collection,
        "ik_hand_pole_r": ik_collection,
        "ik_finger_thumb_r": ik_collection,
        "ik_finger_index_r": ik_collection,
        "ik_finger_middle_r": ik_collection,
        "ik_finger_ring_r": ik_collection,
        "ik_finger_pinky_r": ik_collection,

        "ik_hand_parent_l": ik_collection,
        "ik_hand_target_l": ik_collection,
        "ik_hand_pole_l": ik_collection,
        "ik_finger_thumb_l": ik_collection,
        "ik_finger_index_l": ik_collection,
        "ik_finger_middle_l": ik_collection,
        "ik_finger_ring_l": ik_collection,
        "ik_finger_pinky_l": ik_collection,
        
        "eye_control_parent": face_collection,
        "eye_control_r": face_collection,
        "eye_control_l": face_collection,
    }

    face_root_bones = ["faceAttach", "FACIAL_C_FacialRoot"]
    for bone in pose_bones:
        if len(bone.bone.collections) > 0:
            continue
        
        if explicit_collection := explicit_collection_bones.get(bone.name):
            explicit_collection.assign(bone)
            continue

        if bone.name == "root":
            bone.use_custom_shape_bone_size = False
            bone.color.palette = "THEME01"
            continue

        if "dyn_" in bone.name:
            dyn_collection.assign(bone)
            bone.custom_shape = bpy.data.objects.get("RIG_Dynamic")
            continue
            
        if "twist_" in bone.name:
            deform_collection.assign(bone)
            bone.use_custom_shape_bone_size = False
            continue

        if "deform_" in bone.name:
            deform_collection.assign(bone)
            bone.custom_shape = bpy.data.objects.get('RIG_Tweak')
            bone.custom_shape_scale_xyz = (0.030, 0.030, 0.030) * scale
            bone.use_custom_shape_bone_size = False
            continue
            
        if any(bone.bone.parent_recursive, lambda parent: parent.name in face_root_bones):
            face_collection.assign(bone)
            if not any(["eyelid", "eye_lid"], lambda filter: filter in bone.name.casefold()) and bone.custom_shape is None:
                bone.custom_shape = bpy.data.objects.get("RIG_FaceBone")
            continue
            

        extra_collection.assign(bone)

    collection_colors = {
        main_collection: "THEME09",
        ik_collection: "THEME04",
        dyn_collection: "THEME07",
        extra_collection: "THEME10",
        deform_collection: "THEME03",
        face_collection: "THEME06",
    }
    
    for collection, palette in collection_colors.items():
        for bone in collection.bones:
            pose_bones[bone.name].color.palette = palette
            
    def add_foot_ik_constraints(suffix):
        is_left = suffix == "l"
        ctrl_bone_name = f"ik_foot_ctrl_{suffix}"

        if inner_roll_bone := pose_bones.get(f"ik_foot_roll_inner_{suffix}"):
            copy_rotation = inner_roll_bone.constraints.new("COPY_ROTATION")
            copy_rotation.target = master_skeleton
            copy_rotation.subtarget = ctrl_bone_name
            copy_rotation.use_x = False
            copy_rotation.use_y = True
            copy_rotation.use_z = False
            copy_rotation.target_space = "LOCAL"
            copy_rotation.owner_space = "LOCAL"

            limit_rotation = inner_roll_bone.constraints.new("LIMIT_ROTATION")
            limit_rotation.use_limit_y = True
            limit_rotation.min_y = radians(-180) if is_left else 0
            limit_rotation.max_y = 0 if is_left else radians(180)
            limit_rotation.owner_space = "LOCAL"

        if outer_roll_bone := pose_bones.get(f"ik_foot_roll_outer_{suffix}"):
            copy_rotation = outer_roll_bone.constraints.new("COPY_ROTATION")
            copy_rotation.target = master_skeleton
            copy_rotation.subtarget = ctrl_bone_name
            copy_rotation.use_x = False
            copy_rotation.use_y = True
            copy_rotation.use_z = False
            copy_rotation.target_space = "LOCAL"
            copy_rotation.owner_space = "LOCAL"

            limit_rotation = outer_roll_bone.constraints.new("LIMIT_ROTATION")
            limit_rotation.use_limit_y = True
            limit_rotation.min_y = 0 if is_left else radians(-180)
            limit_rotation.max_y = radians(180) if is_left else 0
            limit_rotation.owner_space = "LOCAL"

        if front_roll_bone := pose_bones.get(f"ik_foot_roll_front_{suffix}"):
            copy_rotation = front_roll_bone.constraints.new("COPY_ROTATION")
            copy_rotation.target = master_skeleton
            copy_rotation.subtarget = ctrl_bone_name
            copy_rotation.use_x = True
            copy_rotation.use_y = False
            copy_rotation.use_z = False
            copy_rotation.invert_x = True
            copy_rotation.target_space = "LOCAL"
            copy_rotation.owner_space = "LOCAL"

            limit_rotation = front_roll_bone.constraints.new("LIMIT_ROTATION")
            limit_rotation.use_limit_x = True
            limit_rotation.min_x = radians(-180)
            limit_rotation.max_x = 0
            limit_rotation.owner_space = "LOCAL"

        if back_roll_bone := pose_bones.get(f"ik_foot_roll_back_{suffix}"):
            copy_rotation = back_roll_bone.constraints.new("COPY_ROTATION")
            copy_rotation.target = master_skeleton
            copy_rotation.subtarget = ctrl_bone_name
            copy_rotation.use_x = True
            copy_rotation.use_y = False
            copy_rotation.use_z = False
            copy_rotation.invert_x = True
            copy_rotation.target_space = "LOCAL"
            copy_rotation.owner_space = "LOCAL"

            limit_rotation = back_roll_bone.constraints.new("LIMIT_ROTATION")
            limit_rotation.use_limit_x = True
            limit_rotation.min_x = 0
            limit_rotation.max_x = radians(180)
            limit_rotation.owner_space = "LOCAL"

        if ball_bone := pose_bones.get(f"ball_{suffix}"):
            copy_rotation = ball_bone.constraints.new("COPY_ROTATION")
            copy_rotation.target = master_skeleton
            copy_rotation.subtarget = ctrl_bone_name
            copy_rotation.use_x = True
            copy_rotation.use_y = False
            copy_rotation.use_z = False
            copy_rotation.invert_x = True
            copy_rotation.mix_mode = "ADD"
            copy_rotation.target_space = "LOCAL"
            copy_rotation.owner_space = "LOCAL"

            limit_rotation = ball_bone.constraints.new("LIMIT_ROTATION")
            limit_rotation.use_limit_x = True
            limit_rotation.min_x = radians(-180)
            limit_rotation.max_x = 0
            limit_rotation.owner_space = "LOCAL"

    add_foot_ik_constraints("r")
    add_foot_ik_constraints("l")

    ik_bones = [
        ("calf_r", "ik_foot_target_r", "ik_foot_pole_r", 2, False),
        ("calf_l", "ik_foot_target_l", "ik_foot_pole_l", 2, False),
        
        ("lowerarm_r", "ik_hand_target_r", "ik_hand_pole_r", 2, False),
        ("thumb_03_r", "ik_finger_thumb_r", None, 3, True, "Use Finger IK"),
        ("index_03_r", "ik_finger_index_r", None, 4, True, "Use Finger IK"),
        ("middle_03_r", "ik_finger_middle_r", None, 4, True, "Use Finger IK"),
        ("ring_03_r", "ik_finger_ring_r", None, 4, True, "Use Finger IK"),
        ("pinky_03_r", "ik_finger_pinky_r", None, 4, True, "Use Finger IK"),
        ("phantom_thumb_03_r", "ik_finger_thumb_r", None, 3, True, "Use Finger IK"),
        ("phantom_index_03_r", "ik_finger_index_r", None, 4, True, "Use Finger IK"),
        ("phantom_middle_03_r", "ik_finger_middle_r", None, 4, True, "Use Finger IK"),
        ("phantom_ring_03_r", "ik_finger_ring_r", None, 4, True, "Use Finger IK"),
        ("phantom_pinky_03_r", "ik_finger_pinky_r", None, 4, True, "Use Finger IK"),

        ("lowerarm_l", "ik_hand_target_l", "ik_hand_pole_l", 2, False),
        ("thumb_03_l", "ik_finger_thumb_l", None, 3, True, "Use Finger IK"),
        ("index_03_l", "ik_finger_index_l", None, 4, True, "Use Finger IK"),
        ("middle_03_l", "ik_finger_middle_l", None, 4, True, "Use Finger IK"),
        ("ring_03_l", "ik_finger_ring_l", None, 4, True, "Use Finger IK"),
        ("pinky_03_l", "ik_finger_pinky_l", None, 4, True, "Use Finger IK"),
        ("phantom_thumb_03_l", "ik_finger_thumb_l", None, 3, True, "Use Finger IK"),
        ("phantom_index_03_l", "ik_finger_index_l", None, 4, True, "Use Finger IK"),
        ("phantom_middle_03_l", "ik_finger_middle_l", None, 4, True, "Use Finger IK"),
        ("phantom_ring_03_l", "ik_finger_ring_l", None, 4, True, "Use Finger IK"),
        ("phantom_pinky_03_l", "ik_finger_pinky_l", None, 4, True, "Use Finger IK"),

        ("dog_ball_r", "ik_dog_ball_r", "ik_foot_pole_r", 3, True),
        ("dog_ball_l", "ik_dog_ball_l", "ik_foot_pole_l", 3, True),
        ("wolf_ball_r", "ik_wolf_ball_r", "ik_foot_pole_r", 3, True),
        ("wolf_ball_l", "ik_wolf_ball_l", "ik_foot_pole_l", 3, True),
    ]
    
    for bone_name, target_name, pole_name, chain_length, use_rotation, *extra in ik_bones:
        if not (bone := pose_bones.get(bone_name)): continue
        
        constraint = bone.constraints.new("IK")
        constraint.target = master_skeleton
        constraint.subtarget = target_name
        constraint.chain_count = chain_length
        constraint.use_rotation = use_rotation
        
        if pole_name:
            constraint.pole_target = master_skeleton
            constraint.pole_subtarget = pole_name
            constraint.pole_angle = radians(180)
            
        if len(extra) > 0 and (influence_custom_property := extra[0]):
            driver = constraint.driver_add("influence")
            var = driver.driver.variables.new()
            var.name = "Use_Finger_IK"
            var.targets[0].id_type = "ARMATURE"
            var.targets[0].id = armature_data
            var.targets[0].data_path = f"[\"{influence_custom_property}\"]"
            driver.driver.expression = var.name
            
        
    copy_rotation_bones = {
        ("foot_r", "ik_foot_target_r", 1.0, "WORLD"),
        ("foot_l", "ik_foot_target_l", 1.0, "WORLD"),
        ("hand_r", "ik_hand_target_r", 1.0, "WORLD"),
        ("hand_l", "ik_hand_target_l", 1.0, "WORLD"),

        ("dog_thigh_r", "thigh_r", 1.0, "WORLD"),
        ("dog_thigh_l", "thigh_l", 1.0, "WORLD"),
        ("wolf_thigh_r", "thigh_r", 1.0, "WORLD"),
        ("wolf_thigh_l", "thigh_l", 1.0, "WORLD"),

        ("R_eye_lid_upper_mid", "R_eye", 0.25, "LOCAL"),
        ("R_eye_lid_lower_mid", "R_eye", 0.25, "LOCAL"),
        ("L_eye_lid_upper_mid", "L_eye", 0.25, "LOCAL"),
        ("L_eye_lid_lower_mid", "L_eye", 0.25, "LOCAL"),

        ("FACIAL_R_EyelidUpperA", "FACIAL_R_Eye", 0.25, "LOCAL"),
        ("FACIAL_R_EyelidLowerA", "FACIAL_R_Eye", 0.25, "LOCAL"),
        ("FACIAL_L_EyelidUpperA", "FACIAL_L_Eye", 0.25, "LOCAL"),
        ("FACIAL_L_EyelidLowerA", "FACIAL_L_Eye", 0.25, "LOCAL"),
    }
    
    for bone_name, target_name, weight, space in copy_rotation_bones:
        if not (bone := pose_bones.get(bone_name)): continue
        
        constraint = bone.constraints.new("COPY_ROTATION")
        constraint.target = master_skeleton
        constraint.subtarget = target_name
        constraint.influence = weight
        constraint.target_space = space
        constraint.owner_space = space

    track_bones = [
        ("eye_control_parent", "head", 0.285)
    ]

    for bone_name, target_name, head_tail in track_bones:
        if not (bone := pose_bones.get(bone_name)): continue

        constraint = bone.constraints.new('TRACK_TO')
        constraint.target = master_skeleton
        constraint.subtarget = target_name
        constraint.head_tail = head_tail
        constraint.track_axis = 'TRACK_NEGATIVE_Y'
        constraint.up_axis = 'UP_Z'

    lock_track_bones = [
        ('R_eye', 'eye_control_r', ["X", "Z"]),
        ('L_eye', 'eye_control_l', ["X", "Z"]),
        ('FACIAL_R_Eye', 'eye_control_r', ["X", "Z"]),
        ('FACIAL_L_Eye', 'eye_control_l', ["X", "Z"]),
    ]

    for bone_name, target_name, target_axis in lock_track_bones:
        if not (bone := pose_bones.get(bone_name)): continue

        for axis in target_axis:
            constraint = bone.constraints.new('LOCKED_TRACK')
            constraint.target = master_skeleton
            constraint.subtarget = target_name
            constraint.track_axis = 'TRACK_Y'
            constraint.lock_axis = 'LOCK_' + axis

    bones = master_skeleton.data.bones
        
    inherit_rotation_bones = [
        ("spine_01", False),
        ("neck_01", False)
    ]
    
    for bone_name, value in inherit_rotation_bones:
        if not (bone := bones.get(bone_name)): continue
        
        bone.use_inherit_rotation = value
        
        
    hide_bones = [
        "ik_foot_roll_inner_r",
        "ik_foot_roll_outer_r",
        "ik_foot_roll_front_r",
        "ik_foot_roll_back_r",
        "ik_foot_target_r",
        "foot_r",
        "ball_r",
        "ik_dog_ball_r",
        "ik_wolf_ball_r",

        "ik_foot_roll_inner_l",
        "ik_foot_roll_outer_l",
        "ik_foot_roll_front_l",
        "ik_foot_roll_back_l",
        "ik_foot_target_l",
        "foot_l",
        "ball_l",
        "ik_dog_ball_l",
        "ik_wolf_ball_l",

        "hand_r",
        "hand_l",
        
    ]
    
    for bone_name in hide_bones:
        if not (bone := bones.get(bone_name)): continue
        bone.hide = True

    conditional_hide_bones = {
        "ik_finger_thumb_r": not use_finger_ik,
        "ik_finger_index_r": not use_finger_ik,
        "ik_finger_middle_r": not use_finger_ik,
        "ik_finger_ring_r": not use_finger_ik,
        "ik_finger_pinky_r": not use_finger_ik,
    
        "ik_finger_thumb_l": not use_finger_ik,
        "ik_finger_index_l": not use_finger_ik,
        "ik_finger_middle_l": not use_finger_ik,
        "ik_finger_ring_l": not use_finger_ik,
        "ik_finger_pinky_l": not use_finger_ik,
    }

    for bone_name, condition in conditional_hide_bones.items():
        if not (bone := bones.get(bone_name)): continue
        bone.hide = condition

    bpy.ops.object.mode_set(mode='OBJECT')
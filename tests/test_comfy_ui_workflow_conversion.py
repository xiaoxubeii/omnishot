import unittest

from app.comfy_ui_workflow import adapt_api_workflow_for_local_runtime, convert_frontend_workflow_to_api
from scripts.generate_bindings_from_api_json import build_bindings


OBJECT_INFO = {
    "LoadImage": {
        "input": {
            "required": {
                "image": [["example.png"]],
                "upload": [["image"]],
                "subfolder": [[""]],
            }
        },
        "input_order": {"required": ["image", "upload", "subfolder"]},
    },
    "DualCLIPLoader": {
        "input": {
            "required": {
                "clip_name1": [["clip_l.safetensors"]],
                "clip_name2": [["t5xxl_fp8.safetensors"]],
                "type": [["flux"]],
                "device": [["default"]],
            }
        },
        "input_order": {"required": ["clip_name1", "clip_name2", "type", "device"]},
    },
    "CLIPTextEncode": {
        "input": {
            "required": {
                "clip": ["CLIP", {}],
                "text": ["STRING", {}],
            }
        },
        "input_order": {"required": ["clip", "text"]},
    },
    "UNETLoader": {
        "input": {
            "required": {
                "unet_name": [["model.safetensors"]],
                "weight_dtype": [["default"]],
            }
        },
        "input_order": {"required": ["unet_name", "weight_dtype"]},
    },
    "KSampler": {
        "input": {
            "required": {
                "model": ["MODEL", {}],
                "positive": ["CONDITIONING", {}],
                "negative": ["CONDITIONING", {}],
                "latent_image": ["LATENT", {}],
                "seed": ["INT", {}],
                "control_after_generate": [["randomize"]],
                "steps": ["INT", {}],
                "cfg": ["FLOAT", {}],
                "sampler_name": [["euler"]],
                "scheduler": [["normal"]],
                "denoise": ["FLOAT", {}],
            }
        },
        "input_order": {
            "required": [
                "model",
                "positive",
                "negative",
                "latent_image",
                "seed",
                "control_after_generate",
                "steps",
                "cfg",
                "sampler_name",
                "scheduler",
                "denoise",
            ]
        },
    },
    "SaveImage": {
        "input": {
            "required": {
                "images": ["IMAGE", {}],
                "filename_prefix": ["STRING", {}],
            }
        },
        "input_order": {"required": ["images", "filename_prefix"]},
    },
}


FRONTEND_WORKFLOW = {
    "nodes": [
        {
            "id": 1,
            "type": "LoadImage",
            "inputs": [],
            "widgets_values": ["product.png", "image", ""],
        },
        {
            "id": 2,
            "type": "DualCLIPLoader",
            "inputs": [],
            "widgets_values": ["clip_l.safetensors", "t5xxl_fp8.safetensors", "flux", "default"],
        },
        {
            "id": 3,
            "type": "CLIPTextEncode",
            "inputs": [
                {"name": "clip", "link": 10},
                {"name": "text", "widget": {"name": "text"}, "link": None},
            ],
            "widgets_values": ["luxury ecommerce product photo"],
        },
        {
            "id": 4,
            "type": "UNETLoader",
            "inputs": [],
            "widgets_values": ["F.1 Kontext dev_fp8", "default"],
        },
        {
            "id": 5,
            "type": "KSampler",
            "inputs": [
                {"name": "model", "link": 11},
                {"name": "positive", "link": 12},
                {"name": "negative", "link": 12},
                {"name": "latent_image", "link": 13},
            ],
            "widgets_values": [927087083425061, "randomize", 30, 1, "euler", "normal", 1],
        },
        {
            "id": 6,
            "type": "SaveImage",
            "inputs": [
                {"name": "images", "link": 14},
            ],
            "widgets_values": ["ComfyUI"],
        },
    ],
    "links": [
        [10, 2, 0, 3, 0, "CLIP"],
        [11, 4, 0, 5, 0, "MODEL"],
        [12, 3, 0, 5, 1, "CONDITIONING"],
        [13, 1, 0, 5, 3, "LATENT"],
        [14, 5, 0, 6, 0, "IMAGE"],
    ],
}


class ConvertFrontendWorkflowToApiTests(unittest.TestCase):
    def test_convert_frontend_workflow_to_api_preserves_links_and_widget_values(self) -> None:
        workflow = convert_frontend_workflow_to_api(FRONTEND_WORKFLOW, OBJECT_INFO)

        self.assertEqual(workflow["1"]["class_type"], "LoadImage")
        self.assertEqual(workflow["1"]["inputs"]["image"], "product.png")
        self.assertEqual(workflow["2"]["inputs"]["clip_name1"], "clip_l.safetensors")
        self.assertEqual(workflow["3"]["inputs"]["clip"], ["2", 0])
        self.assertEqual(workflow["3"]["inputs"]["text"], "luxury ecommerce product photo")
        self.assertEqual(workflow["4"]["inputs"]["unet_name"], "F.1 Kontext dev_fp8")
        self.assertEqual(workflow["5"]["inputs"]["model"], ["4", 0])
        self.assertEqual(workflow["5"]["inputs"]["seed"], 927087083425061)
        self.assertEqual(workflow["5"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(workflow["6"]["inputs"]["images"], ["5", 0])
        self.assertEqual(workflow["6"]["inputs"]["filename_prefix"], "ComfyUI")

    def test_converted_workflow_can_be_detected_by_bindings_generator(self) -> None:
        workflow = convert_frontend_workflow_to_api(FRONTEND_WORKFLOW, OBJECT_INFO)
        bindings = build_bindings(workflow)

        self.assertEqual(bindings["image"], [{"node_id": "1", "input_name": "image"}])
        self.assertEqual(bindings["positive_prompt"], [{"node_id": "3", "input_name": "text"}])
        self.assertEqual(bindings["seed"], [{"node_id": "5", "input_name": "seed"}])
        self.assertEqual(bindings["preferred_output_nodes"], ["6"])

    def test_convert_frontend_workflow_to_api_synthesizes_hidden_control_after_generate(self) -> None:
        object_info = {
            **OBJECT_INFO,
            "KSampler": {
                "input": {
                    "required": {
                        "model": ["MODEL", {}],
                        "seed": ["INT", {"control_after_generate": True}],
                        "steps": ["INT", {}],
                        "cfg": ["FLOAT", {}],
                        "sampler_name": [["euler"]],
                        "scheduler": [["normal"]],
                        "positive": ["CONDITIONING", {}],
                        "negative": ["CONDITIONING", {}],
                        "latent_image": ["LATENT", {}],
                        "denoise": ["FLOAT", {}],
                    }
                },
                "input_order": {
                    "required": [
                        "model",
                        "seed",
                        "steps",
                        "cfg",
                        "sampler_name",
                        "scheduler",
                        "positive",
                        "negative",
                        "latent_image",
                        "denoise",
                    ]
                },
            },
        }

        workflow = convert_frontend_workflow_to_api(FRONTEND_WORKFLOW, object_info)

        self.assertEqual(workflow["5"]["inputs"]["seed"], 927087083425061)
        self.assertEqual(workflow["5"]["inputs"]["control_after_generate"], "randomize")
        self.assertEqual(workflow["5"]["inputs"]["steps"], 30)
        self.assertEqual(workflow["5"]["inputs"]["cfg"], 1)
        self.assertEqual(workflow["5"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(workflow["5"]["inputs"]["scheduler"], "normal")
        self.assertEqual(workflow["5"]["inputs"]["denoise"], 1)

    def test_adapt_api_workflow_for_local_runtime_rewrites_missing_kontext_dependencies(self) -> None:
        object_info = {
            "DualCLIPLoader": {
                "input": {
                    "required": {
                        "clip_name1": [["clip_l.safetensors", "t5xxl_fp8.safetensors"]],
                        "clip_name2": [["clip_l.safetensors", "t5xxl_fp8.safetensors"]],
                        "type": [["flux"]],
                    },
                    "optional": {
                        "device": [["default", "cpu"]],
                    },
                },
                "input_order": {"required": ["clip_name1", "clip_name2", "type"], "optional": ["device"]},
            },
            "UNETLoader": {
                "input": {
                    "required": {
                        "unet_name": [[]],
                        "weight_dtype": [["default"]],
                    }
                },
                "input_order": {"required": ["unet_name", "weight_dtype"]},
            },
            "UnetLoaderGGUF": {
                "input": {
                    "required": {
                        "unet_name": [["flux1-dev-Q4_K_S.gguf"]],
                    }
                },
                "input_order": {"required": ["unet_name"]},
            },
            "LoraLoader": {
                "input": {
                    "required": {
                        "model": ["MODEL", {}],
                        "clip": ["CLIP", {}],
                        "lora_name": [[]],
                        "strength_model": ["FLOAT", {}],
                        "strength_clip": ["FLOAT", {}],
                    }
                },
                "input_order": {
                    "required": ["model", "clip", "lora_name", "strength_model", "strength_clip"]
                },
            },
        }
        workflow = {
            "49": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": ["61", 0],
                    "clip": ["55", 1],
                },
            },
            "50": {
                "class_type": "ReferenceLatent",
                "inputs": {
                    "conditioning": ["49", 0],
                    "latent": ["58", 0],
                },
            },
            "51": {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "clip_l",
                    "clip_name2": "t5xxl_fp8_e4m3fn",
                    "type": "flux",
                    "device": "default",
                },
            },
            "52": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.sft"}},
            "53": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["49", 0]}},
            "54": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "F.1 Kontext dev_fp8",
                    "weight_dtype": "default",
                },
            },
            "55": {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": ["54", 0],
                    "clip": ["51", 0],
                    "lora_name": "private-kontext-lora",
                    "strength_model": 0.8,
                    "strength_clip": 1,
                },
            },
            "56": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["55", 0],
                    "seed": 123,
                    "control_after_generate": "fixed",
                    "steps": 30,
                    "cfg": 1,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "positive": ["62", 0],
                    "negative": ["53", 0],
                    "latent_image": ["66", 0],
                    "denoise": 1,
                },
            },
            "57": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["65", 0]}},
            "58": {"class_type": "VAEEncode", "inputs": {"pixels": ["57", 0], "vae": ["52", 0]}},
            "59": {"class_type": "VAEDecode", "inputs": {"samples": ["56", 0], "vae": ["52", 0]}},
            "61": {"class_type": "LibLibTranslate", "inputs": {}},
            "62": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["50", 0], "guidance": 2.5}},
            "63": {"class_type": "SaveImage", "inputs": {"images": ["59", 0], "filename_prefix": "ComfyUI"}},
            "65": {"class_type": "LoadImage", "inputs": {"image": "request.png"}},
            "66": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1536, "batch_size": 1}},
        }

        adapted = adapt_api_workflow_for_local_runtime(workflow, object_info)

        self.assertEqual(adapted["51"]["inputs"]["clip_name1"], "clip_l.safetensors")
        self.assertEqual(adapted["51"]["inputs"]["clip_name2"], "t5xxl_fp8.safetensors")
        self.assertEqual(adapted["54"]["class_type"], "UnetLoaderGGUF")
        self.assertEqual(adapted["54"]["inputs"], {"unet_name": "flux1-dev-Q4_K_S.gguf"})
        self.assertEqual(adapted["49"]["inputs"]["text"], "")
        self.assertEqual(adapted["49"]["inputs"]["clip"], ["51", 0])
        self.assertEqual(adapted["62"]["inputs"]["conditioning"], ["49", 0])
        self.assertEqual(adapted["56"]["inputs"]["model"], ["54", 0])
        self.assertEqual(adapted["56"]["inputs"]["latent_image"], ["58", 0])
        self.assertEqual(adapted["56"]["inputs"]["denoise"], 0.55)
        self.assertNotIn("50", adapted)
        self.assertNotIn("55", adapted)
        self.assertNotIn("61", adapted)
        self.assertNotIn("66", adapted)

    def test_adapt_api_workflow_for_local_runtime_preserves_reference_latent_when_kontext_gguf_exists(self) -> None:
        object_info = {
            "DualCLIPLoader": {
                "input": {
                    "required": {
                        "clip_name1": [["clip_l.safetensors", "t5xxl_fp8.safetensors"]],
                        "clip_name2": [["clip_l.safetensors", "t5xxl_fp8.safetensors"]],
                        "type": [["flux"]],
                    },
                    "optional": {
                        "device": [["default", "cpu"]],
                    },
                },
                "input_order": {"required": ["clip_name1", "clip_name2", "type"], "optional": ["device"]},
            },
            "UNETLoader": {
                "input": {
                    "required": {
                        "unet_name": [[]],
                        "weight_dtype": [["default"]],
                    }
                },
                "input_order": {"required": ["unet_name", "weight_dtype"]},
            },
            "UnetLoaderGGUF": {
                "input": {
                    "required": {
                        "unet_name": [["flux1-dev-Q4_K_S.gguf", "flux1-kontext-dev-Q4_K_S.gguf"]],
                    }
                },
                "input_order": {"required": ["unet_name"]},
            },
            "LoraLoader": {
                "input": {
                    "required": {
                        "model": ["MODEL", {}],
                        "clip": ["CLIP", {}],
                        "lora_name": [[]],
                        "strength_model": ["FLOAT", {}],
                        "strength_clip": ["FLOAT", {}],
                    }
                },
                "input_order": {
                    "required": ["model", "clip", "lora_name", "strength_model", "strength_clip"]
                },
            },
        }
        workflow = {
            "49": {"class_type": "CLIPTextEncode", "inputs": {"text": ["61", 0], "clip": ["55", 1]}},
            "50": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["49", 0], "latent": ["58", 0]}},
            "51": {
                "class_type": "DualCLIPLoader",
                "inputs": {"clip_name1": "clip_l", "clip_name2": "t5xxl_fp8_e4m3fn", "type": "flux", "device": "default"},
            },
            "52": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.sft"}},
            "53": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["49", 0]}},
            "54": {"class_type": "UNETLoader", "inputs": {"unet_name": "F.1 Kontext dev_fp8", "weight_dtype": "default"}},
            "55": {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": ["54", 0],
                    "clip": ["51", 0],
                    "lora_name": "private-kontext-lora",
                    "strength_model": 0.8,
                    "strength_clip": 1,
                },
            },
            "56": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["55", 0],
                    "seed": 123,
                    "control_after_generate": "fixed",
                    "steps": 30,
                    "cfg": 1,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "positive": ["62", 0],
                    "negative": ["53", 0],
                    "latent_image": ["66", 0],
                    "denoise": 1,
                },
            },
            "57": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["65", 0]}},
            "58": {"class_type": "VAEEncode", "inputs": {"pixels": ["57", 0], "vae": ["52", 0]}},
            "59": {"class_type": "VAEDecode", "inputs": {"samples": ["56", 0], "vae": ["52", 0]}},
            "61": {"class_type": "LibLibTranslate", "inputs": {}},
            "62": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["50", 0], "guidance": 2.5}},
            "63": {"class_type": "SaveImage", "inputs": {"images": ["59", 0], "filename_prefix": "ComfyUI"}},
            "65": {"class_type": "LoadImage", "inputs": {"image": "request.png"}},
            "66": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1536, "batch_size": 1}},
        }

        adapted = adapt_api_workflow_for_local_runtime(workflow, object_info)

        self.assertEqual(adapted["54"]["class_type"], "UnetLoaderGGUF")
        self.assertEqual(adapted["54"]["inputs"], {"unet_name": "flux1-kontext-dev-Q4_K_S.gguf"})
        self.assertEqual(adapted["49"]["inputs"]["text"], "")
        self.assertEqual(adapted["49"]["inputs"]["clip"], ["51", 0])
        self.assertEqual(adapted["62"]["inputs"]["conditioning"], ["50", 0])
        self.assertEqual(adapted["56"]["inputs"]["latent_image"], ["66", 0])
        self.assertEqual(adapted["56"]["inputs"]["denoise"], 1)
        self.assertIn("50", adapted)
        self.assertIn("66", adapted)
        self.assertNotIn("55", adapted)
        self.assertNotIn("61", adapted)

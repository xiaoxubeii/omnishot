SCENE_PRESETS = [
    {
        "name": "sunset_bedroom_window",
        "title": "落日卧室窗边",
        "prompt_template": (
            "{product_brief}, placed near a bedroom window, golden sunset rim light, "
            "soft premium lifestyle styling, realistic commercial shadows, elegant editorial mood"
        ),
        "negative_prompt": (
            "blurry, low quality, duplicate product, deformed garment, changed product silhouette, "
            "extra straps, extra objects attached to product, watermark, text"
        ),
    },
    {
        "name": "morning_balcony_fresh",
        "title": "清晨露台",
        "prompt_template": (
            "{product_brief}, arranged on a bright balcony table, fresh morning sunlight, airy atmosphere, "
            "natural reflection control, clean luxury ecommerce photography"
        ),
        "negative_prompt": (
            "blurry, low quality, duplicate product, deformed garment, changed product silhouette, "
            "watermark, text"
        ),
    },
    {
        "name": "hotel_suite_warmth",
        "title": "酒店套房暖光",
        "prompt_template": (
            "{product_brief}, styled in a high-end hotel suite, warm tungsten practical lights, "
            "rich contrast, premium hospitality mood, refined fabric sheen"
        ),
        "negative_prompt": (
            "blurry, low quality, duplicate product, deformed garment, changed product silhouette, "
            "messy clutter, watermark, text"
        ),
    },
    {
        "name": "studio_softbox_catalog",
        "title": "棚拍目录风",
        "prompt_template": (
            "{product_brief}, clean studio catalogue shot, three-point softbox lighting, "
            "controlled highlight rolloff, subtle gradient backdrop, premium retail finish"
        ),
        "negative_prompt": (
            "blurry, low quality, duplicate product, deformed garment, changed product silhouette, "
            "watermark, text"
        ),
    },
    {
        "name": "vanity_evening_glamour",
        "title": "梳妆台夜景",
        "prompt_template": (
            "{product_brief}, near a vanity mirror with bulb lights, glamorous evening ambience, "
            "beauty editorial composition, warm reflections, polished commercial aesthetic"
        ),
        "negative_prompt": (
            "blurry, low quality, duplicate product, deformed garment, changed product silhouette, "
            "watermark, text"
        ),
    },
    {
        "name": "rainy_window_storytelling",
        "title": "雨窗氛围",
        "prompt_template": (
            "{product_brief}, placed near a rainy window, cool overcast daylight mixed with warm indoor fill, "
            "cinematic storytelling, premium luxury campaign lighting"
        ),
        "negative_prompt": (
            "blurry, low quality, duplicate product, deformed garment, changed product silhouette, "
            "watermark, text"
        ),
    },
]


EDIT_PRESETS = [
    {
        "name": "camera_left_45",
        "title": "左转 45 度",
        "prompt_template": (
            "Move the camera to the left and rotate 45 degrees to the left. "
            "Keep the exact same product identity, fabric, trim, logo, and proportions. "
            "Photorealistic premium ecommerce product photography."
        ),
        "negative_prompt": (
            "different product, changed silhouette, changed length, changed neckline, changed sleeve, "
            "extra accessories, duplicate object, broken geometry, blurry, low quality, watermark, text"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "camera_right_45",
        "title": "右转 45 度",
        "prompt_template": (
            "Move the camera to the right and rotate 45 degrees to the right. "
            "Keep the exact same product identity, fabric, trim, logo, and proportions. "
            "Photorealistic premium ecommerce product photography."
        ),
        "negative_prompt": (
            "different product, changed silhouette, changed length, changed neckline, changed sleeve, "
            "extra accessories, duplicate object, broken geometry, blurry, low quality, watermark, text"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "top_down",
        "title": "俯视镜头",
        "prompt_template": (
            "Turn the camera to a top-down view. Keep the exact same product identity, shape, fabric sheen, "
            "and material details. Premium ecommerce product editing."
        ),
        "negative_prompt": (
            "different product, changed silhouette, changed color, broken geometry, blurry, low quality, watermark, text"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "close_up_detail",
        "title": "特写细节",
        "prompt_template": (
            "Turn the camera to a close-up shot focusing on the garment texture and sewing details. "
            "Keep the exact same product identity and material behavior. Premium ecommerce detail shot."
        ),
        "negative_prompt": (
            "different product, changed texture, fake embroidery, extra accessories, blurry, low quality, watermark, text"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "wide_angle_context",
        "title": "广角氛围",
        "prompt_template": (
            "Turn the camera to a wide-angle lens while keeping the product as the hero subject. "
            "Retain the same product identity, silhouette, and fabric characteristics. "
            "Luxury editorial ecommerce image."
        ),
        "negative_prompt": (
            "different product, tiny subject, changed silhouette, deformed shape, blurry, low quality, watermark, text"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "editorial_light_shift",
        "title": "仅改光线",
        "prompt_template": (
            "Keep the same camera angle and the exact same product identity. "
            "Only restyle the lighting into polished luxury editorial light with realistic highlights and shadows."
        ),
        "negative_prompt": (
            "different product, changed pose, changed silhouette, changed trim, duplicate object, blurry, low quality, watermark, text"
        ),
        "use_angle_lora": False,
    },
]


CATALOG_PROFILES = [
    {
        "name": "sleepwear_luxury",
        "title": "睡裙电商主推",
        "description": (
            "针对丝绸/缎面睡裙、吊带裙、居家轻奢睡衣。优先输出卧室、露台、酒店暖光和模特上身多角度图。"
        ),
        "product_brief": "premium silk nightdress, satin slip dress, luxury sleepwear ecommerce product photo",
        "scene_presets": [
            "sunset_bedroom_window",
            "morning_balcony_fresh",
            "hotel_suite_warmth",
            "vanity_evening_glamour",
        ],
        "tryon_templates": ["woman_1", "woman_2"],
        "edit_presets": ["editorial_light_shift", "camera_left_45", "camera_right_45", "close_up_detail"],
        "tryon_angle_presets": ["camera_left_45", "camera_right_45"],
        "cloth_type": "overall",
        "edit_extra_prompt": (
            "Preserve the exact same sleepwear silhouette, hem length, neckline, lace trim, and silky drape. "
            "Emphasize refined fabric sheen and premium ecommerce styling."
        ),
        "tryon_angle_extra_prompt": (
            "Maintain graceful sleepwear presentation, elegant drape, clean premium studio styling, "
            "and realistic high-end fashion lighting."
        ),
    },
    {
        "name": "lingerie_editorial",
        "title": "内衣 / 贴身服饰",
        "description": (
            "用于更强调材质、贴身剪裁和灯光轮廓的内衣或性感家居服商品图。"
        ),
        "product_brief": "premium lingerie or intimate apparel ecommerce product photo with refined material detail",
        "scene_presets": [
            "studio_softbox_catalog",
            "vanity_evening_glamour",
            "rainy_window_storytelling",
        ],
        "tryon_templates": ["woman_1"],
        "edit_presets": ["editorial_light_shift", "close_up_detail", "camera_left_45"],
        "tryon_angle_presets": ["camera_left_45", "close_up_detail"],
        "cloth_type": "upper",
        "edit_extra_prompt": (
            "Keep the exact same garment fit, strap construction, cup shape, lace placement, and premium material behavior."
        ),
        "tryon_angle_extra_prompt": (
            "Keep the same model identity and the same intimate garment fit. Focus on elegance, realism, and clean editorial lighting."
        ),
    },
    {
        "name": "apparel_catalog",
        "title": "常规服饰目录",
        "description": (
            "适合普通女装、上装、连衣裙的稳定目录图批量生成，兼顾场景图、模特图和多角度。"
        ),
        "product_brief": "premium apparel ecommerce product photo with clean retail styling",
        "scene_presets": [
            "studio_softbox_catalog",
            "morning_balcony_fresh",
            "hotel_suite_warmth",
        ],
        "tryon_templates": ["woman_1", "woman_2", "woman_3"],
        "edit_presets": ["camera_left_45", "camera_right_45", "editorial_light_shift"],
        "tryon_angle_presets": ["camera_left_45", "camera_right_45"],
        "cloth_type": "overall",
        "edit_extra_prompt": (
            "Keep the exact same garment identity, retail-ready shape, stitching, and fabric behavior."
        ),
        "tryon_angle_extra_prompt": (
            "Retain the same model, same garment fit, same proportions, and same commercial retail styling."
        ),
    },
]

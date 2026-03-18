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

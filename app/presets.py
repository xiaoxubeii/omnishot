SCENE_PRESETS = [
    {
        "name": "sunset_bedroom_window",
        "title": "落日卧室窗边",
        "prompt_template": (
            "{product_brief}，放在卧室窗边，带有金色落日边缘光，"
            "柔和高级生活方式布景，真实商业级阴影，优雅杂志氛围"
        ),
        "negative_prompt": (
            "模糊，低质量，重复商品，服装变形，商品轮廓改变，"
            "多余肩带，商品上附着多余物体，水印，文字"
        ),
    },
    {
        "name": "morning_balcony_fresh",
        "title": "清晨露台",
        "prompt_template": (
            "{product_brief}，摆放在明亮的露台桌面上，清晨自然阳光，空气感氛围，"
            "自然反射控制，干净高级的电商摄影"
        ),
        "negative_prompt": (
            "模糊，低质量，重复商品，服装变形，商品轮廓改变，"
            "水印，文字"
        ),
    },
    {
        "name": "hotel_suite_warmth",
        "title": "酒店套房暖光",
        "prompt_template": (
            "{product_brief}，置于高端酒店套房场景，暖色钨丝灯实景光源，"
            "层次丰富的明暗对比，高级酒店感氛围，精致面料光泽"
        ),
        "negative_prompt": (
            "模糊，低质量，重复商品，服装变形，商品轮廓改变，"
            "背景杂乱，水印，文字"
        ),
    },
    {
        "name": "studio_softbox_catalog",
        "title": "棚拍目录风",
        "prompt_template": (
            "{product_brief}，干净棚拍目录图，三点柔光箱布光，"
            "高光过渡受控，细腻渐变背景，高级零售成片质感"
        ),
        "negative_prompt": (
            "模糊，低质量，重复商品，服装变形，商品轮廓改变，"
            "水印，文字"
        ),
    },
    {
        "name": "vanity_evening_glamour",
        "title": "梳妆台夜景",
        "prompt_template": (
            "{product_brief}，靠近带灯泡的梳妆镜，夜晚华丽氛围，"
            "美妆杂志式构图，温暖反射，精致商业美学"
        ),
        "negative_prompt": (
            "模糊，低质量，重复商品，服装变形，商品轮廓改变，"
            "水印，文字"
        ),
    },
    {
        "name": "rainy_window_storytelling",
        "title": "雨窗氛围",
        "prompt_template": (
            "{product_brief}，置于雨窗旁，冷调阴天日光混合室内暖补光，"
            "电影感叙事氛围，高级广告灯光"
        ),
        "negative_prompt": (
            "模糊，低质量，重复商品，服装变形，商品轮廓改变，"
            "水印，文字"
        ),
    },
]


EDIT_PRESETS = [
    {
        "name": "camera_left_45",
        "title": "左转 45 度",
        "prompt_template": (
            "镜头向左移动并左转 45 度。"
            "保持完全相同的商品身份、面料、辅料、标志和比例。"
            "照片级真实，高级电商商品摄影。"
        ),
        "negative_prompt": (
            "不同商品，轮廓改变，长度改变，领口改变，袖型改变，"
            "多余配饰，重复物体，几何结构损坏，模糊，低质量，水印，文字"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "camera_right_45",
        "title": "右转 45 度",
        "prompt_template": (
            "镜头向右移动并右转 45 度。"
            "保持完全相同的商品身份、面料、辅料、标志和比例。"
            "照片级真实，高级电商商品摄影。"
        ),
        "negative_prompt": (
            "不同商品，轮廓改变，长度改变，领口改变，袖型改变，"
            "多余配饰，重复物体，几何结构损坏，模糊，低质量，水印，文字"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "top_down",
        "title": "俯视镜头",
        "prompt_template": (
            "把镜头切换到俯视视角。保持完全相同的商品身份、外形、面料光泽"
            "和材质细节。高级电商商品编辑图。"
        ),
        "negative_prompt": (
            "不同商品，轮廓改变，颜色改变，几何结构损坏，模糊，低质量，水印，文字"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "close_up_detail",
        "title": "特写细节",
        "prompt_template": (
            "将镜头切到服装纹理与缝线细节特写。"
            "保持完全相同的商品身份和材质表现。高级电商细节图。"
        ),
        "negative_prompt": (
            "不同商品，纹理改变，假刺绣，多余配饰，模糊，低质量，水印，文字"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "wide_angle_context",
        "title": "广角氛围",
        "prompt_template": (
            "把镜头切换为广角，同时保持商品仍然是主体。"
            "保留相同的商品身份、轮廓和面料特征。"
            "高级杂志感电商图片。"
        ),
        "negative_prompt": (
            "不同商品，主体过小，轮廓改变，形状变形，模糊，低质量，水印，文字"
        ),
        "use_angle_lora": True,
    },
    {
        "name": "editorial_light_shift",
        "title": "仅改光线",
        "prompt_template": (
            "保持相同机位和完全相同的商品身份。"
            "只重塑灯光为高级杂志式光线，保留真实高光与阴影。"
        ),
        "negative_prompt": (
            "不同商品，姿态改变，轮廓改变，辅料改变，重复物体，模糊，低质量，水印，文字"
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
        "product_brief": "高端真丝睡裙，缎面吊带裙，轻奢睡衣电商商品主图",
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
            "保持完全相同的睡裙轮廓、下摆长度、领口、蕾丝辅料和丝滑垂感。"
            "强调精致面料光泽和高级电商陈列感。"
        ),
        "tryon_angle_extra_prompt": (
            "保持优雅的睡裙展示效果、自然垂坠、干净高级棚拍风格，"
            "以及真实的高端时尚灯光。"
        ),
    },
    {
        "name": "lingerie_editorial",
        "title": "内衣 / 贴身服饰",
        "description": (
            "用于更强调材质、贴身剪裁和灯光轮廓的内衣或性感家居服商品图。"
        ),
        "product_brief": "高端内衣或贴身服饰电商商品主图，强调精致材质细节",
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
            "保持完全相同的服装贴合度、肩带结构、杯型、蕾丝位置和高级材质表现。"
        ),
        "tryon_angle_extra_prompt": (
            "保持相同的模特身份和相同的贴身服饰贴合效果，重点表现优雅、真实和干净的杂志式灯光。"
        ),
    },
    {
        "name": "apparel_catalog",
        "title": "常规服饰目录",
        "description": (
            "适合普通女装、上装、连衣裙的稳定目录图批量生成，兼顾场景图、模特图和多角度。"
        ),
        "product_brief": "高端常规服饰电商商品主图，零售陈列风格干净利落",
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
            "保持完全相同的服装身份、零售成衣轮廓、缝线结构和面料表现。"
        ),
        "tryon_angle_extra_prompt": (
            "保持相同模特、相同穿着贴合度、相同比例和相同商业零售风格。"
        ),
    },
]

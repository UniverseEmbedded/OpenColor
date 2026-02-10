import os
import cairosvg
from pathlib import Path
from PIL import Image


from oc_core_02.utils.logger import get_logger

logger = get_logger(__name__)
def convert_svg_to_png():
    svg_path = Path(__file__).parent.parent / "data" / "icon.svg"
    icons_dir = Path(__file__).parent / "src-tauri" / "icons"
    
    if not svg_path.exists():
        raise FileNotFoundError(f"找不到 SVG 文件: {svg_path}")
    
    if not icons_dir.exists():
        icons_dir.mkdir(parents=True)
    
    sizes = [
        ("32x32.png", 32),
        ("128x128.png", 128),
        ("128x128@2x.png", 256),
        ("icon.png", 1024),
        ("Square107x107Logo.png", 107),
        ("Square142x142Logo.png", 142),
        ("Square150x150Logo.png", 150),
        ("Square284x284Logo.png", 284),
        ("Square30x30Logo.png", 30),
        ("Square310x310Logo.png", 310),
        ("Square44x44Logo.png", 44),
        ("Square71x71Logo.png", 71),
        ("Square89x89Logo.png", 89),
        ("StoreLogo.png", 50),
    ]
    
    for filename, size in sizes:
        output_path = icons_dir / filename
        logger.info(f"正在转换 {filename} (尺寸: {size}x{size})...")
        try:
            cairosvg.svg2png(
                url=str(svg_path),
                write_to=str(output_path),
                output_width=size,
                output_height=size
            )
            logger.info(f"成功生成: {output_path}")
        except Exception as e:
            logger.info(f"转换 {filename} 时出错: {e}")
            raise

    # 生成 .ico 文件
    logger.info("正在生成 icon.ico...")
    try:
        img = Image.open(icons_dir / "icon.png")
        # ICO 通常包含多种尺寸
        ico_sizes = [(64, 64), (128, 128), (256, 256)]
        img.save(icons_dir / "icon.ico", format='ICO', sizes=ico_sizes)
        logger.info(f"成功生成: {icons_dir / 'icon.ico'}")
    except Exception as e:
        logger.info(f"生成 icon.ico 时出错: {e}")
        raise

    # 生成 .icns 文件
    logger.info("正在生成 icon.icns...")
    try:
        img = Image.open(icons_dir / "icon.png")
        # ICNS 自动处理尺寸
        img.save(icons_dir / "icon.icns", format='ICNS')
        logger.info(f"成功生成: {icons_dir / 'icon.icns'}")
    except Exception as e:
        logger.info(f"生成 icon.icns 时出错: {e}")
        # 有些系统可能不支持 ICNS 导出，或者需要特定尺寸
        # 如果 1024x1024 不行，尝试 512x512
        try:
            img_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
            img_512.save(icons_dir / "icon.icns", format='ICNS')
            logger.info(f"尝试 512x512 成功生成: {icons_dir / 'icon.icns'}")
        except Exception as e2:
             logger.info(f"再次尝试生成 icon.icns 时出错: {e2}")
             raise

if __name__ == "__main__":
    convert_svg_to_png()
    logger.info("所有图标转换完成！")

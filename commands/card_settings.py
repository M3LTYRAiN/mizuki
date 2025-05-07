import re
import disnake
from disnake.ext import commands
from bot import bot, get_user_card_settings, update_user_card_settings
import io
from PIL import Image, ImageDraw, ImageFont

@bot.slash_command(
    name="배경색상",
    description="레벨 카드의 배경 그라데이션 색상을 설정하는 것이다."
)
async def set_background_color(
    inter: disnake.ApplicationCommandInteraction,
    상단색상: str = commands.Param(description="상단 색상 코드 (예: FF5733, 9BBAFF)"),
    하단색상: str = commands.Param(description="하단 색상 코드 (예: AAB5F5, 5733FF)")
):
    # 색상 코드 유효성 검증 함수
    def is_valid_color(color):
        if not color:
            return False
        # RGB 색상 코드(6자리) 또는 RGBA 색상 코드(8자리)
        if re.match(r'^[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$', color):
            return True
        return False
    
    # 색상 코드 앞에 # 붙이기
    top_color = f"#{상단색상}" if 상단색상 and not 상단색상.startswith('#') else 상단색상
    bottom_color = f"#{하단색상}" if 하단색상 and not 하단색상.startswith('#') else 하단색상
    
    # 하단색상이 없으면 상단색상과 동일하게 설정
    if not bottom_color:
        bottom_color = top_color
    
    # 색상 코드 유효성 검증
    if not is_valid_color(상단색상) or (하단색상 and not is_valid_color(하단색상)):
        await inter.response.send_message(
            "❌ 잘못된 색상 코드인 것이다. 유효한 HEX 색상 코드를 입력하는 것이다. (예: FF5733)",
            ephemeral=True
        )
        return
    
    # 색상 설정 적용
    guild_id = inter.guild.id
    user_id = inter.author.id
    
    # 기존 설정 로드
    current_settings = get_user_card_settings(guild_id, user_id)
    
    # 설정 업데이트
    new_settings = {
        "bg_color_top": top_color,
        "bg_color_bottom": bottom_color,
        "card_style": current_settings.get("card_style", "default")
    }
    
    # DB에 저장
    success = update_user_card_settings(guild_id, user_id, new_settings)
    
    if success:
        # 미리보기 이미지 생성
        preview_image = await create_preview_image(top_color, bottom_color)
        
        await inter.response.send_message(
            f"✅ 배경 색상이 설정된 것이다.\n상단: `{top_color}` | 하단: `{bottom_color}`",
            file=disnake.File(fp=preview_image, filename="preview.png"),
            ephemeral=True  # 메시지를 본인만 볼 수 있게 설정
        )
    else:
        await inter.response.send_message(
            "❌ 설정 저장 중 오류가 발생한 것이다.",
            ephemeral=True
        )

async def create_preview_image(top_color, bottom_color):
    """색상 미리보기 이미지 생성"""
    width, height = 400, 100
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    
    # HEX 색상을 RGB로 변환
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    try:
        top_rgb = hex_to_rgb(top_color)
        bottom_rgb = hex_to_rgb(bottom_color)
    except (ValueError, TypeError):
        # 기본값으로 대체
        top_rgb = (155, 190, 255)  # 연한 하늘색
        bottom_rgb = (170, 181, 245)  # 연한 보라색
    
    # 그라데이션 배경 적용
    for y in range(height):
        progress = y / height
        r = int(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * progress)
        g = int(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * progress)
        b = int(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * progress)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # 이미지를 바이트 스트림으로 변환
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)
    
    return image_bytes

import math
import disnake
from disnake.ext import commands
from bot import bot, server_chat_counts, conn, c
from bot import get_user_card_settings  # 추가된 import
import io
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import random
import datetime

# 레벨 테이블 생성
def setup_level_table():
    c.execute('''CREATE TABLE IF NOT EXISTS user_levels (
                    guild_id INTEGER,
                    user_id INTEGER,
                    level INTEGER DEFAULT 0,
                    xp INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    last_updated DATETIME,
                    PRIMARY KEY (guild_id, user_id)
                )''')
    conn.commit()
    print("Level table initialized")

# 레벨 시스템 초기화
setup_level_table()

# XP 계산 함수 - 장기적 성장 곡선 적용
# 하루 500회 채팅 × 365일 × 4년 = 약 730,000회 (레벨 100)
# 각 메시지 = 5 XP 기준, 총 3,650,000 XP
def calculate_xp_for_level(level):
    # 멱함수 기반: BASE × (level)^EXPONENT
    BASE = 40
    EXPONENT = 2.5
    
    return int(BASE * (level ** EXPONENT))

# 레벨 계산 함수 - 주어진 XP로 레벨 계산
def calculate_level_from_xp(xp):
    # 역계산: level = (xp/BASE)^(1/EXPONENT)
    BASE = 40
    EXPONENT = 2.5
    
    if xp <= 0:
        return 0
    
    level = (xp / BASE) ** (1 / EXPONENT)
    return math.floor(level)

# 채팅 횟수에서 레벨 계산 함수
def calculate_level_from_chat_count(chat_count):
    # 채팅 1회 = 5 XP로 변환 후 계산
    xp = chat_count * 5
    return calculate_level_from_xp(xp)

# 다음 레벨까지 필요한 총 XP 계산
def calculate_xp_needed_for_next_level(current_level):
    return calculate_xp_for_level(current_level + 1)

# 사용자의 레벨 정보 가져오기 (수정됨)
def get_user_level_info(guild_id, user_id):
    # 데이터베이스에서 레벨 정보 조회
    c.execute("""
        SELECT level, xp, total_messages FROM user_levels
        WHERE guild_id = ? AND user_id = ?
    """, (guild_id, user_id))
    
    row = c.fetchone()
    
    if row:
        level, xp, total_msgs = row
    else:
        # 사용자 데이터가 없으면 chat_counts에서 총 메시지 수 가져와서 레벨 계산
        total_msgs = get_chat_count(guild_id, user_id)
        xp = total_msgs * 5  # 채팅 1회당 5 XP
        level = calculate_level_from_xp(xp)
        
        # 새 사용자 정보 저장
        c.execute("""
            INSERT INTO user_levels (guild_id, user_id, level, xp, total_messages, last_updated)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (guild_id, user_id, level, xp, total_msgs))
        conn.commit()
    
    # 다음 레벨까지 필요한 XP 계산
    xp_for_current = calculate_xp_for_level(level)
    xp_for_next = calculate_xp_for_level(level + 1)
    xp_progress = xp - xp_for_current
    xp_needed = xp_for_next - xp_for_current
    
    # 진행률 계산
    progress = xp_progress / xp_needed if xp_needed > 0 else 0
    
    # 다음 레벨까지 필요한 채팅 횟수 (XP÷5)
    chats_needed = math.ceil((xp_for_next - xp) / 5)
    
    return {
        "level": level,
        "xp": xp,
        "total_messages": total_msgs,
        "xp_for_current": xp_for_current,
        "xp_for_next": xp_for_next,
        "xp_progress": xp_progress,
        "xp_needed": xp_needed,
        "progress": progress,
        "chats_needed": chats_needed
    }

# 채팅 횟수 가져오기
def get_chat_count(guild_id, user_id):
    # 1. 메모리 캐시에서 확인
    if guild_id in server_chat_counts and user_id in server_chat_counts[guild_id]:
        return server_chat_counts[guild_id][user_id]
    
    # 2. 데이터베이스에서 직접 조회
    c.execute("SELECT count FROM chat_counts WHERE guild_id = ? AND user_id = ?", 
              (guild_id, user_id))
    row = c.fetchone()
    if row:
        return row[0]
    
    return 0  # 데이터가 없으면 0 반환

# 메시지 이벤트에서 레벨 업데이트 함수 (수정됨)
def update_user_level(guild_id, user_id):
    # 현재 레벨 정보 가져오기
    c.execute("""
        SELECT level, xp, total_messages FROM user_levels
        WHERE guild_id = ? AND user_id = ?
    """, (guild_id, user_id))
    
    row = c.fetchone()
    
    if row:
        current_level, current_xp, total_msgs = row
        # 메시지 수와 XP 증가
        total_msgs += 1
        current_xp += 5  # 메시지당 5 XP
        
        # 새 레벨 계산
        new_level = calculate_level_from_xp(current_xp)
        
        # 데이터 업데이트
        c.execute("""
            UPDATE user_levels 
            SET level = ?, xp = ?, total_messages = ?, last_updated = CURRENT_TIMESTAMP
            WHERE guild_id = ? AND user_id = ?
        """, (new_level, current_xp, total_msgs, guild_id, user_id))
        conn.commit()
        
        # 레벨업 여부 반환
        return new_level > current_level
    
    else:
        # 새 사용자 초기화
        c.execute("""
            INSERT INTO user_levels (guild_id, user_id, level, xp, total_messages, last_updated)
            VALUES (?, ?, 0, 5, 1, CURRENT_TIMESTAMP)
        """, (guild_id, user_id))
        conn.commit()
        return False

async def create_level_card(member, level_info, join_date, days_in_server):
    """레벨 정보를 표시하는 이미지 카드를 생성하는 것이다."""
    # 이미지 크기는 그대로 유지
    width, height = 800, 340
    
    # 기본 이미지 생성
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    
    # 사용자별 카드 설정 로드
    card_settings = get_user_card_settings(member.guild.id, member.id)
    
    # 배경 그라데이션 (사용자 설정 색상 사용)
    bg_top = card_settings["bg_color_top"]
    bg_bottom = card_settings["bg_color_bottom"]
    
    def hex_to_rgb(hex_color):
        """HEX 색상 코드를 RGB로 변환"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    # 색상 유효성 검증 및 변환
    try:
        top_rgb = hex_to_rgb(bg_top)
        bottom_rgb = hex_to_rgb(bg_bottom)
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
    
    # 폰트 설정 - 가독성을 위해 크기 조정
    font_path = "/Users/Luna/Desktop/chatzipbot/OTF/ONE Mobile POP.ttf"
    font_name = ImageFont.truetype(font_path, 42)  # 이름 폰트
    font_level = ImageFont.truetype(font_path, 36)  # 레벨 폰트 약간 키움
    font_info = ImageFont.truetype(font_path, 24)  # 정보 폰트 약간 키움
    font_small = ImageFont.truetype(font_path, 20)  # 작은 폰트도 약간 키움
    font_server = ImageFont.truetype(font_path, 20)  # 서버 이름 폰트
    deco_font = ImageFont.truetype(font_path, 20)  # 장식 폰트 추가 - 이 라인 추가
    
    # 레이아웃 영역 정의 (여백 유지)
    padding = 25
    
    # 프로필 이미지 처리를 위한 변수 정의
    avatar_size = 150
    avatar_x = padding
    avatar_y = (height - avatar_size) // 2
    border_width = 4  # 테두리 두께 약간 키움
    
    # 장식 색상과 투명도 설정
    def hex_to_rgba(hex_color, alpha=50):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:  # RGB 형식
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)
        return (255, 255, 255, alpha)  # 기본 흰색 반투명
    
    # 장식 색상 목록
    deco_colors = {
        "diamond": "#D4E8FF",  # 연한 파랑
        "star": "#DCD4FF",     # 연한 보라
        "circle": "#D4FFEC"    # 연한 민트
    }
    
    # 프로필 영역 계산 (장식이 이 영역에 겹치지 않도록)
    profile_area = {
        'x1': avatar_x - 10,
        'y1': avatar_y - 10,
        'x2': avatar_x + avatar_size + border_width*2 + 20,
        'y2': avatar_y + avatar_size + border_width*2 + 20
    }
    
    # 정보 영역 - 프로필 이미지 오른쪽에 텍스트 배치 (장식 함수에서 필요)
    info_x = avatar_x + avatar_size + border_width*2 + 30
    
    # 장식 추가 함수
    def add_decorations(symbol, count, color_hex):
        color = hex_to_rgba(color_hex)
        for _ in range(count):
            # 랜덤 위치 생성
            x = random.randint(0, width)
            y = random.randint(0, height)
            
            # 프로필 사진 영역이나 텍스트 영역은 피함
            if (profile_area['x1'] < x < profile_area['x2'] and 
                profile_area['y1'] < y < profile_area['y2']):
                continue
            
            # 오른쪽 정보 영역도 피함 (정보 시작 지점 + 약간의 여백)
            if x > info_x - 20:
                # 오른쪽 지역이 70% 확률로 스킵됨
                if random.random() < 0.7:
                    continue
            
            # 장식 그리기
            draw.text((x, y), symbol, font=deco_font, fill=color, anchor="mm")
    
    # 다이아몬드, 별, 원 장식 추가
    add_decorations("◆", 6, deco_colors["diamond"])  # 다이아몬드 6개
    add_decorations("★", 7, deco_colors["star"])     # 별 7개
    add_decorations("●", 5, deco_colors["circle"])   # 원 5개
    
    # 프로필 이미지 처리 - 테두리 개선
    try:
        avatar = await member.avatar.read()
        avatar_image = Image.open(io.BytesIO(avatar)).convert('RGBA')
        avatar_image = avatar_image.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
        
        # 둥근 마스크 (약간의 둥근 모서리만)
        mask = Image.new('L', (avatar_size, avatar_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        corner_radius = 20  # 더 자연스러운 둥근 모서리
        mask_draw.rounded_rectangle((0, 0, avatar_size, avatar_size), corner_radius, fill=255)
        
        # 마스크 적용
        masked_avatar = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
        masked_avatar.paste(avatar_image, (0, 0), mask)
        
        # 테두리 추가 - 더 세련된 테두리로 변경
        border = Image.new('RGBA', (avatar_size + border_width*2, avatar_size + border_width*2), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.rounded_rectangle(
            [(0, 0), (border.width-1, border.height-1)],
            corner_radius + border_width,
            outline=(255, 255, 255, 230),  # 불투명도 증가
            width=border_width
        )
        
        # 약간의 테두리 그림자 효과 추가
        shadow = Image.new('RGBA', (avatar_size + border_width*2 + 6, avatar_size + border_width*2 + 6), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle(
            [(3, 3), (shadow.width-4, shadow.height-4)],
            corner_radius + border_width + 3,
            fill=(0, 0, 0, 30)  # 매우 연한 그림자
        )
        image.paste(shadow, (avatar_x - 3, avatar_y - 3), shadow)
        
        # 테두리와 이미지 합성
        final_avatar = Image.new('RGBA', border.size, (0, 0, 0, 0))
        final_avatar.paste(border, (0, 0), border)
        final_avatar.paste(masked_avatar, (border_width, border_width), masked_avatar)
        
        # 이미지 배치
        image.paste(final_avatar, (avatar_x, avatar_y), final_avatar)
    except Exception as e:
        print(f"프로필 이미지 처리 오류: {e}")
    
    # 상단 이름 배치 - 그림자 개선
    name = member.display_name
    name_y = avatar_y + 5
    
    # 이름 테두리 효과 개선 - 더 부드럽게
    for dx, dy in [(dx/1.5, dy/1.5) for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (-1, 0), (1, 0), (0, -1), (0, 1)]]:
        draw.text(
            (info_x + dx, name_y + dy), 
            name, 
            font=font_name, 
            fill=(0, 0, 0, 60)  # 불투명도 낮춤
        )
    
    # 이름 최대 너비 계산 (카드 끝에서 여백 뺀 길이)
    name_max_width = width - info_x - padding
    
    # 이름 길이 확인 및 폰트 크기 조정 - 최소 크기 증가
    name_width = draw.textlength(name, font=font_name)
    if name_width > name_max_width:
        adjusted_size = int(42 * (name_max_width / name_width))  # 36 -> 42로 변경
        adjusted_size = max(24, adjusted_size)  # 최소 크기 20 -> 24로 증가
        font_name = ImageFont.truetype(font_path, adjusted_size)
    
    # 이름 텍스트에 더 강한 테두리 효과 적용
    for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (-1.5, 0), (1.5, 0), (0, -1.5), (0, 1.5)]:
        draw.text(
            (info_x + dx, name_y + dy), 
            name, 
            font=font_name, 
            fill=(0, 0, 0, 100)  # 테두리 불투명도 약간 증가
        )
    
    # 이름 텍스트 그리기
    draw.text(
        (info_x, name_y), 
        name, 
        font=font_name, 
        fill=(255, 255, 255)
    )
    
    # 레벨 정보 - 더 눈에 띄게
    level_y = name_y + font_name.size + 20  # 간격 약간 늘림
    level_text = f"레벨 {level_info['level']}"
    
    # 레벨 텍스트 배경 추가 (강조)
    level_width = draw.textlength(level_text, font=font_level) + 30
    level_height = font_level.size + 10
    level_bg = Image.new('RGBA', (int(level_width), level_height), (0, 0, 0, 0))
    level_bg_draw = ImageDraw.Draw(level_bg)
    level_bg_draw.rounded_rectangle(
        [(0, 0), (level_width-1, level_height-1)],
        radius=level_height//2,
        fill=(255, 225, 120, 40)  # 매우 연한 금색 배경
    )
    image.paste(level_bg, (info_x - 15, level_y - 5), level_bg)
    
    # 레벨 테두리 효과 - 더 섬세하게
    for dx, dy in [(dx/2, dy/2) for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2)]]:
        draw.text(
            (info_x + dx, level_y + dy), 
            level_text, 
            font=font_level, 
            fill=(0, 0, 0, 80)
        )
    
    # 레벨 텍스트 (금색 개선)
    draw.text(
        (info_x, level_y), 
        level_text, 
        font=font_level, 
        fill=(255, 225, 120)
    )
    
    # 프로그레스 바 완전 재디자인
    progress_y = level_y + font_level.size + 25  # 간격 약간 늘림
    
    # 프로그레스 바 크기
    progress_width = int((width - info_x - padding * 2) * 0.7)  # 약간 더 넓게
    progress_height = 12  # 약간 얇게
    
    # 프로그레스 바 배경 (더 세련된 디자인)
    draw.rounded_rectangle(
        [(info_x, progress_y), (info_x + progress_width, progress_y + progress_height)],
        radius=progress_height // 2,
        fill=(255, 255, 255, 150)  # 반투명 흰색
    )
    
    # 채워진 프로그레스 바 - 검은색으로 단순화
    filled_width = int(progress_width * level_info['progress'])
    if filled_width > 0:
        # 마스크 생성 - 정확히 같은 크기로 조정
        mask = Image.new('L', (filled_width, progress_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle(
            [(0, 0), (filled_width-1, progress_height-1)],  # -1로 정확한 크기 맞춤
            radius=progress_height // 2,
            fill=255
        )
        
        # 검은색 바로 변경 (그라데이션 제거)
        filled_bar = Image.new('RGBA', (filled_width, progress_height), (0, 0, 0, 200))  # 불투명한 검정색
        filled_bar.putalpha(mask)
        image.paste(filled_bar, (info_x, progress_y), filled_bar)
    
    # 진행률 및 남은 채팅 정보 - 더 깔끔하게
    progress_percent = int(level_info['progress'] * 100)
    # XP를 채팅 횟수로 변경 (XP ÷ 5)
    current_chats = math.ceil((level_info['xp'] - level_info['xp_for_current']) / 5)
    total_needed_chats = math.ceil(level_info['xp_needed'] / 5)
    progress_info_text = f"{current_chats}/{total_needed_chats} 채팅"
    
    progress_info_x = info_x + progress_width + 15
    progress_info_y = progress_y + (progress_height // 2)
    
    # 텍스트 그림자 효과 (가독성 향상)
    draw.text(
        (progress_info_x, progress_info_y),
        progress_info_text,
        font=font_info,
        fill=(255, 255, 255, 200),  # 약간 불투명하게
        anchor="lm",  # 왼쪽 중앙 정렬
        stroke_width=2,  # 얇은 외곽선 추가
        stroke_fill=(0, 0, 0, 50)  # 매우 연한 검정 외곽선
    )
    
    # 정보 섹션 개선 - 네모 박스 제거하고 텍스트만 표시
    stats_y = progress_y + progress_height + 20  # 간격 약간 늘림
    
    # 채팅 정보 아이콘 - 위치 상향 조정
    chat_y = stats_y - 5  # 약간 위로 이동
    
    # 이모지 대신 텍스트 사용 - 작은 폰트로 변경
    draw.text(
        (info_x, chat_y),
        "채팅:",  # 💬 이모지 대신 "채팅:" 텍스트 사용
        font=font_small,  # font_info에서 font_small로 변경
        fill=(255, 255, 255)
    )
    
    total_chats_text = f"{level_info['total_messages']}회"
    draw.text(
        (info_x + 70, chat_y),  # x좌표 증가 (60 -> 70)
        total_chats_text,
        font=font_info,
        fill=(255, 255, 255)
    )
    
    # 가입일 정보 아이콘 - 위치 상향 조정
    date_y = chat_y + 30  # 채팅 정보보다 아래지만 기존보다는 위로
    
    # 이모지 대신 텍스트 사용 - 작은 폰트로 변경
    draw.text(
        (info_x, date_y),
        "가입일:",  # 📆 이모지 대신 "가입일:" 텍스트 사용 
        font=font_small,  # font_info에서 font_small로 변경
        fill=(255, 255, 255)
    )
    
    join_date_str = f"{join_date.strftime('%y/%m/%d')} (+{days_in_server}일)"
    draw.text(
        (info_x + 70, date_y),  # x좌표 증가 (60 -> 70)
        join_date_str,
        font=font_info,
        fill=(255, 240, 130)  # 밝은 노란색 유지
    )
    
    # 서버 아이콘과 이름 표시 (새로 추가)
    try:
        # 서버 아이콘 불러오기
        server_icon_size = 28
        if member.guild.icon:  # 서버 아이콘이 있는지 확인
            server_icon = await member.guild.icon.read()
            server_icon_image = Image.open(io.BytesIO(server_icon)).convert('RGBA')
            server_icon_image = server_icon_image.resize((server_icon_size, server_icon_size), Image.Resampling.LANCZOS)
            
            # 서버 아이콘 위치 - 유저 프로필 왼쪽 시작점과 정렬
            server_icon_x = avatar_x
            server_icon_y = padding
            
            # 둥근 마스크 적용
            mask = Image.new('L', (server_icon_size, server_icon_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, server_icon_size, server_icon_size), fill=255)
            
            # 마스크 적용하여 서버 아이콘 둥글게
            masked_icon = Image.new('RGBA', server_icon_image.size, (0, 0, 0, 0))
            masked_icon.paste(server_icon_image, (0, 0), mask)
            
            # 서버 아이콘 붙여넣기
            image.paste(masked_icon, (server_icon_x, server_icon_y), masked_icon)
            
            # 서버 이름 표시 - 아이콘 오른쪽
            server_name = member.guild.name
            server_name_x = server_icon_x + server_icon_size + 8
            server_name_y = server_icon_y + server_icon_size//2
            
            # 서버 이름이 너무 길면 자르기
            max_server_name_width = width - server_name_x - padding
            if draw.textlength(server_name, font=font_server) > max_server_name_width:
                while draw.textlength(server_name + "...", font=font_server) > max_server_name_width and len(server_name) > 0:
                    server_name = server_name[:-1]
                server_name += "..."
            
            # 서버 이름 그림자 효과 (가독성 향상)
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                draw.text(
                    (server_name_x + dx, server_name_y + dy),
                    server_name,
                    font=font_server,
                    fill=(0, 0, 0, 80),
                    anchor="lm"  # 왼쪽 중앙 정렬
                )
            
            # 서버 이름 그리기
            draw.text(
                (server_name_x, server_name_y),
                server_name,
                font=font_server,
                fill=(255, 255, 255),
                anchor="lm"  # 왼쪽 중앙 정렬
            )
    except Exception as e:
        print(f"서버 아이콘 처리 오류: {e}")
    
    # 이미지를 바이트 스트림으로 변환
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)
    
    return image_bytes

# 텍스트 폰트 크기 조정 함수
def get_fitting_font_size(text, max_width, font_path, start_size, min_size=18):
    """텍스트가 주어진 너비에 맞도록 폰트 크기를 조절하는 함수"""
    font = ImageFont.truetype(font_path, start_size)
    img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(img)
    text_width = draw.textlength(text, font=font)
    
    if text_width <= max_width:
        return start_size
    
    # 텍스트가 너무 길면 크기 줄이기
    current_size = start_size
    while current_size > min_size and text_width > max_width:
        current_size -= 2
        font = ImageFont.truetype(font_path, current_size)
        text_width = draw.textlength(text, font=font)
    
    return current_size

@bot.slash_command(
    name="레벨",
    description="자신의 채팅 레벨을 확인하는 것이다."
)
async def level(inter: disnake.ApplicationCommandInteraction, 
                멤버: disnake.Member = None):
    # 멤버 파라미터가 없으면 명령어 사용자로 설정
    target_member = 멤버 or inter.author
    guild_id = inter.guild.id
    
    # 응답 지연
    await inter.response.defer()
    
    # 레벨 정보 가져오기
    level_info = get_user_level_info(guild_id, target_member.id)
    
    # 서버 가입일 정보
    join_date = target_member.joined_at
    today = datetime.datetime.now(join_date.tzinfo)
    days_in_server = (today - join_date).days
    
    # 레벨 카드 이미지 생성
    image_bytes = await create_level_card(target_member, level_info, join_date, days_in_server)
    
    # 이미지 전송
    await inter.followup.send(
        file=disnake.File(fp=image_bytes, filename="level_card.png")
    )

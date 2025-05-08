import disnake
from disnake.ext import commands
from bot import bot, server_roles
import database as db  # MongoDB 모듈 임포트

# 역할 원래 색상 정보를 저장하는 딕셔너리 (메모리 캐시)
role_original_colors = {}

@bot.slash_command(name="역할색상", description="1등 역할의 색상을 변경하는 것이다.")
@commands.has_permissions(administrator=True)
async def 역할색상(inter: disnake.ApplicationCommandInteraction, color: str):
    try:
        # 색상 검증 (16진수 형식)
        if not color.startswith("#"):
            color = f"#{color}"
        
        # 색상 변환
        try:
            color_int = int(color[1:], 16)
            discord_color = disnake.Color(color_int)
        except ValueError:
            await inter.response.send_message("❌ 올바른 색상 코드를 입력하는 것이다. (예: #FF5733)", ephemeral=True)
            return
        
        # 서버 역할 확인
        guild_id = inter.guild.id
        if guild_id not in server_roles:
            await inter.response.send_message("❌ 역할이 설정되지 않았습니다. /역할설정 명령어를 사용하는 것이다.", ephemeral=True)
            return
        
        # 1등 역할 가져오기
        first_role_id = server_roles[guild_id]["first"]
        first_role = inter.guild.get_role(first_role_id)
        if not first_role:
            await inter.response.send_message("❌ 설정된 1등 역할을 찾을 수 없는 것이다.", ephemeral=True)
            return
        
        # 원래 색상 저장 (MongoDB)
        original_color = first_role.color.value
        if db.is_mongo_connected():
            # 서버와 역할별로 원래 색상 저장
            save_role_original_color(guild_id, first_role_id, original_color)
        
        # 역할 색상 변경
        await first_role.edit(color=discord_color)
        await inter.response.send_message(f"✅ 1등 역할({first_role.name})의 색상이 {color}로 변경된 것이다.", ephemeral=True)
        
    except Exception as e:
        await inter.response.send_message(f"❌ 오류가 발생한 것이다: {e}", ephemeral=True)

def save_role_original_color(guild_id, role_id, color):
    """역할의 원래 색상을 MongoDB에 저장합니다"""
    if not db.is_mongo_connected():
        return
    
    # 컬렉션이 없다면 생성
    if not hasattr(db, 'role_colors_collection'):
        db.role_colors_collection = db.db.role_colors
        
    # 역할의 원래 색상 저장
    db.role_colors_collection.update_one(
        {"guild_id": guild_id, "role_id": role_id},
        {"$set": {
            "original_color": color,
            "updated_at": db.datetime.now(db.timezone.utc)
        }},
        upsert=True
    )
    
    # 메모리 캐시도 업데이트
    if guild_id not in role_original_colors:
        role_original_colors[guild_id] = {}
    role_original_colors[guild_id][role_id] = color

def restore_role_original_color(guild, role):
    """역할의 원래 색상을 복원합니다"""
    guild_id = guild.id
    role_id = role.id
    
    # 1. 메모리 캐시 확인
    if guild_id in role_original_colors and role_id in role_original_colors[guild_id]:
        return role_original_colors[guild_id][role_id]
    
    # 2. MongoDB에서 확인
    if db.is_mongo_connected():
        if not hasattr(db, 'role_colors_collection'):
            db.role_colors_collection = db.db.role_colors
            
        doc = db.role_colors_collection.find_one({"guild_id": guild_id, "role_id": role_id})
        if doc and "original_color" in doc:
            # 메모리 캐시 업데이트
            if guild_id not in role_original_colors:
                role_original_colors[guild_id] = {}
            role_original_colors[guild_id][role_id] = doc["original_color"]
            return doc["original_color"]
    
    # 3. 둘 다 없으면 현재 색상 반환
    return role.color.value

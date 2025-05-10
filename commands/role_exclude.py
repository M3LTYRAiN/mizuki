from disnake.ext import commands
import disnake
from bot import bot, server_excluded_roles
import database as db

@bot.slash_command(name="역할제외", description="서버에서 역할을 제외하거나 해제하는 것이다.")
@commands.has_permissions(administrator=True)
async def 역할제외(
    inter: disnake.ApplicationCommandInteraction,
    action: str = commands.Param(choices=["추가", "제거"], description="추가 또는 제거"),
    role: disnake.Role = commands.Param(description="역할 선택"),
):
    guild_id = inter.guild.id
    print(f"[역할제외] 명령어 실행 - 서버: {guild_id}, 작업: {action}, 역할: {role.id} ({role.name})")
    
    # 현재 메모리 상태 확인 및 초기화
    if guild_id not in server_excluded_roles:
        server_excluded_roles[guild_id] = []
        print(f"[역할제외] 서버 {guild_id}의 제외 역할 목록 초기화")
    
    print(f"[역할제외] 현재 제외 역할 목록: {server_excluded_roles[guild_id]}")
    
    # MongoDB에 메모리 상태와 동기화 확인
    if db.is_mongo_connected():
        try:
            db_excluded_roles = db.get_guild_excluded_roles(guild_id)
            print(f"[역할제외] DB에서 불러온 제외 역할: {db_excluded_roles}")
            
            # DB에 데이터가 있고 메모리와 다르면 동기화
            if db_excluded_roles and set(db_excluded_roles) != set(server_excluded_roles[guild_id]):
                print(f"[역할제외] 메모리와 DB 데이터 불일치, 동기화 중...")
                server_excluded_roles[guild_id] = db_excluded_roles.copy()
        except Exception as e:
            print(f"[역할제외] DB 조회 중 오류: {e}")
    
    if action == "추가":
        if role.id not in server_excluded_roles[guild_id]:
            server_excluded_roles[guild_id].append(role.id)
            await inter.response.send_message(f"✅ {role.name} 역할이 제외 목록에 추가된 것이다.", ephemeral=True)
            
            # MongoDB에 저장 및 로그 출력
            print(f"[역할제외] 역할 추가 - 서버: {guild_id}, 역할: {role.id} ({role.name})")
            if db.is_mongo_connected():
                db.save_excluded_role_data(guild_id, server_excluded_roles[guild_id])
                print(f"[역할제외] DB 저장 완료: {server_excluded_roles[guild_id]}")
        else:
            await inter.response.send_message(f"❌ {role.name} 역할은 이미 제외 목록에 있는 것이다.", ephemeral=True)

    elif action == "제거":
        if role.id in server_excluded_roles[guild_id]:
            server_excluded_roles[guild_id].remove(role.id)
            await inter.response.send_message(f"✅ {role.name} 역할이 제외 목록에서 제거된 것이다.", ephemeral=True)
            
            # MongoDB에 저장 및 로그 출력
            print(f"[역할제외] 역할 제거 - 서버: {guild_id}, 역할: {role.id} ({role.name})")
            if db.is_mongo_connected():
                db.save_excluded_role_data(guild_id, server_excluded_roles[guild_id])
                print(f"[역할제외] DB 저장 완료: {server_excluded_roles[guild_id]}")
        else:
            await inter.response.send_message(f"❌ {role.name} 역할은 제외 목록에 없는 것이다.", ephemeral=True)

    print(f"[역할제외] 작업 완료 후 제외 역할 목록: {server_excluded_roles[guild_id]}")
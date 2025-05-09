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
    print(f"[역할제외] 현재 메모리 상태 (시작): {server_excluded_roles.get(guild_id, [])}")

    if action == "추가":
        # 메모리에 길드 ID가 없으면 초기화
        if guild_id not in server_excluded_roles:
            server_excluded_roles[guild_id] = []

        # 역할 ID가 이미 있는지 확인
        if role.id not in server_excluded_roles[guild_id]:
            server_excluded_roles[guild_id].append(role.id)
            await inter.response.send_message(f"✅ {role.name} 역할이 제외 목록에 추가된 것이다.", ephemeral=True)

            # MongoDB에 저장 및 로그 출력
            print(f"[역할제외] 역할 추가 - 서버: {guild_id}, 역할: {role.id} ({role.name})")
            if db.is_mongo_connected():
                db.save_excluded_role_data(guild_id, server_excluded_roles[guild_id])
                print(f"[역할제외] MongoDB 저장 후 메모리 상태: {server_excluded_roles[guild_id]}")
            else:
                print("⚠️ [역할제외] MongoDB에 연결되지 않아 제외 역할을 저장할 수 없습니다")
        else:
            await inter.response.send_message(f"❌ {role.name} 역할은 이미 제외 목록에 있는 것이다.", ephemeral=True)

    elif action == "제거":
        # 길드와 역할이 모두 있는지 확인
        if guild_id in server_excluded_roles and role.id in server_excluded_roles[guild_id]:
            server_excluded_roles[guild_id].remove(role.id)
            await inter.response.send_message(f"✅ {role.name} 역할이 제외 목록에서 제거된 것이다.", ephemeral=True)

            # MongoDB에 저장 및 로그 출력
            print(f"[역할제외] 역할 제거 - 서버: {guild_id}, 역할: {role.id} ({role.name})")
            if db.is_mongo_connected():
                db.save_excluded_role_data(guild_id, server_excluded_roles[guild_id])
                print(f"[역할제외] MongoDB 저장 후 메모리 상태: {server_excluded_roles[guild_id]}")
            else:
                print("⚠️ [역할제외] MongoDB에 연결되지 않아 제외 역할을 저장할 수 없습니다")
        else:
            await inter.response.send_message(f"❌ {role.name} 역할은 제외 목록에 없는 것이다.", ephemeral=True)

    print(f"[역할제외] 최종 메모리 상태: {server_excluded_roles.get(guild_id, [])}")
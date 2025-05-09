from disnake.ext import commands
import disnake
from bot import bot, server_roles
import database as db

@bot.slash_command(name="역할설정", description="서버에서 사용할 역할을 설정하는 것이다.")
@commands.has_permissions(administrator=True)
async def 역할설정(inter: disnake.ApplicationCommandInteraction, first_role: disnake.Role, other_role: disnake.Role):
    guild_id = inter.guild.id
    print(f"[역할설정] 명령어 실행 - 서버: {guild_id}, 1위 역할: {first_role.id}, 2-6위 역할: {other_role.id}")
    
    # 메모리에 저장
    server_roles[guild_id] = {"first": first_role.id, "other": other_role.id}
    
    # MongoDB에 저장
    try:
        if db.is_mongo_connected():
            db.save_role_data(guild_id, first_role.id, other_role.id)
            print(f"✅ [역할설정] MongoDB 저장 성공 - 서버: {guild_id}")
            
            # 저장 후 바로 확인
            saved_data = db.get_guild_role_data(guild_id)
            if saved_data:
                print(f"✓ 저장된 데이터 확인: {saved_data}")
            else:
                print("⚠️ 저장 후 데이터를 확인할 수 없습니다")
        else:
            print("⚠️ [역할설정] MongoDB에 연결되지 않아 역할 데이터를 저장할 수 없습니다")
    except Exception as e:
        print(f"❌ [역할설정] MongoDB 저장 실패: {e}")
        import traceback
        traceback.print_exc()
    
    await inter.response.send_message(f"✅ 역할 설정 완료: {first_role.name} (1위), {other_role.name} (2~6위)", ephemeral=True)

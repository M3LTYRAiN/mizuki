import disnake
from disnake.ext import commands
from database import save_guild_info  # DB 저장 함수

@commands.slash_command(name="갱신", description="이 서버의 정보를 DB에 즉시 업로드하는 것이다.")
async def 갱신(inter: disnake.ApplicationCommandInteraction):
    await inter.response.defer(with_message=True)

    guild = inter.guild  # 현재 명령어를 호출한 서버 정보

    try:
        save_result = save_guild_info(guild)  # DB에 저장 시도

        if save_result:
            await inter.edit_original_message(content="✅ 서버 정보를 성공적으로 저장한 것이다!")
        else:
            await inter.edit_original_message(content="❌ 정보를 저장하지 못한 것이다. 관리자에게 문의할 것!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        await inter.edit_original_message(content=f"❌ 오류 발생: {str(e)}")

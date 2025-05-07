
import disnake
from disnake.ext import commands
from bot import bot, server_roles, server_excluded_roles

class HelpView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=180.0)  # 3분 타임아웃

    @disnake.ui.button(label="일반 명령어", style=disnake.ButtonStyle.primary)
    async def user_commands(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        embed = disnake.Embed(
            title="🖥️ 일반 명령어",
            color=disnake.Color.blue()
        )
        
        commands = f"""
</리더보드:{bot.application_id}>
• 채팅 순위를 확인합니다
• 이전/다음/나의 순위로 이동할 수 있습니다

</오미쿠지:{bot.application_id}>
• 일본식 운세를 뽑습니다
• 오늘의 운세와 행운의 메시지를 확인할 수 있습니다
        """
        # 레벨과 카드설정 명령어 제거
        embed.description = commands
        embed.set_footer(text="명령어를 클릭하면 바로 사용할 수 있습니다!")
        await inter.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="관리자 명령어", style=disnake.ButtonStyle.danger)
    async def admin_commands(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        embed = disnake.Embed(
            title="⚡ 관리자 전용 명령어",
            description="※ 실행은 관리자만 가능합니다",
            color=disnake.Color.red()
        )
        
        commands = f"""
</집계:{bot.application_id}> `[시작일] [종료일]`
• 채팅 순위를 집계하고 역할을 부여합니다
• 날짜: YYYYMMDD 또는 't'(오늘)

</역할설정:{bot.application_id}> `[1등역할] [2-6등역할]`
• 집계 시 부여할 역할을 설정합니다

</역할제외:{bot.application_id}> `[추가/제거] [역할]`
• 집계에서 제외할 역할을 관리합니다

</연속초기화:{bot.application_id}>
• 모든 연속 기록을 초기화합니다

</역할색상:{bot.application_id}> `[색상]`
• 1등 역할의 색상을 변경합니다
• HEX 색상코드로 입력 (예: #FF5733)
• 관리자 또는 1등 역할 보유자만 사용 가능
        """
        # 레벨역할설정 명령어 제거
        embed.description = commands
        embed.set_footer(text="⚠️ 관리자 권한이 필요한 명령어입니다")
        await inter.response.edit_message(embed=embed, view=self)

    @disnake.ui.button(label="현재 설정", style=disnake.ButtonStyle.secondary)
    async def current_settings(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        guild_id = inter.guild.id
        embed = disnake.Embed(
            title="⚙️ 현재 설정",
            color=disnake.Color.light_grey()
        )

        # 역할 설정 확인
        if guild_id in server_roles:
            first_role = inter.guild.get_role(server_roles[guild_id]["first"])
            other_role = inter.guild.get_role(server_roles[guild_id]["other"])
            roles_text = f"1등 역할: {first_role.mention if first_role else '미설정'}\n"
            roles_text += f"2-6등 역할: {other_role.mention if other_role else '미설정'}"
        else:
            roles_text = "설정된 역할이 없습니다."
        embed.add_field(name="역할 설정", value=roles_text, inline=False)

        # 제외된 역할 확인
        if guild_id in server_excluded_roles and server_excluded_roles[guild_id]:
            excluded = [inter.guild.get_role(role_id) for role_id in server_excluded_roles[guild_id]]
            excluded_text = ", ".join(role.mention for role in excluded if role is not None)
        else:
            excluded_text = "없음"
        embed.add_field(name="제외된 역할", value=excluded_text, inline=False)
        
        # 레벨 역할 확인 섹션 제거
        
        embed.set_footer(text="역할 설정은 관리자만 변경할 수 있습니다.")
        await inter.response.edit_message(embed=embed, view=self)

@bot.slash_command(name="도움말", description="챗집봇의 명령어 도움말을 보여주는 것이다.")
async def 도움말(inter: disnake.ApplicationCommandInteraction):
    view = HelpView()
    embed = disnake.Embed(
        title="📚 도움말",
        description="원하는 명령어 카테고리를 선택하세요",
        color=disnake.Color.green()
    )
    await inter.response.send_message(embed=embed, view=view, ephemeral=True)
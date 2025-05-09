import disnake
from disnake.ext import commands
from bot import bot
import os

class ManualView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=180.0)  # 3분 타임아웃
        self.current_page = 0
        self.category = "user"  # 기본 카테고리: 일반 유저

        # 이미지 폴더 이름 정의 (현재 스크립트와 같은 폴더 내 'manual' 폴더를 가정)
        self.image_folder = "manual"

        # 카테고리별 이미지 목록 (레벨 관련 이미지 제거)
        self.images = {
            "user": ["리더보드.png", "오미쿠지.png"],  # 레벨.png, 카드설정.png 제거
            "admin": ["a역할설정.png", "a역할제외.png", "a역할초기화.png", "a집계.png"],  # a레벨역할설정.png 제거
            "first": ["f역할색상.png"]
        }

        # 카테고리별 제목
        self.category_titles = {
            "user": "📘 일반 사용자 명령어",
            "admin": "🔧 관리자 전용 명령어",
            "first": "👑 1등 전용 명령어"
        }

    def get_current_file_path(self):
        """현재 카테고리와 페이지에 해당하는 이미지 파일 경로 반환"""
        if 0 <= self.current_page < len(self.images[self.category]):
            filename = self.images[self.category][self.current_page]
            return os.path.join(self.image_folder, filename)
        return None

    def get_current_command_name(self):
        """현재 이미지의 명령어 이름 반환"""
        if 0 <= self.current_page < len(self.images[self.category]):
            filename = self.images[self.category][self.current_page]
            # 파일명에서 확장자 제거
            return filename.replace('.png', '')
        return "알 수 없음"

    def update_buttons(self):
        """현재 상태에 맞게 버튼 상태 업데이트"""
        # 이전 버튼 상태 설정
        self.children[0].disabled = (self.current_page <= 0)

        # 다음 버튼 상태 설정
        self.children[1].disabled = (self.current_page >= len(self.images[self.category]) - 1)

        # 카테고리 버튼 상태 설정 (현재 카테고리는 비활성화)
        for i, cat in enumerate(["user", "admin", "first"]):
            self.children[i+2].disabled = (self.category == cat)

    async def update_message(self, interaction):
        """메시지 업데이트"""
        file_path = self.get_current_file_path()

        if file_path and os.path.exists(file_path):
            # 이미지를 파일로 첨부
            file = disnake.File(file_path, filename="manual.png")

            # 임베드 생성
            embed = disnake.Embed(
                title=f"{self.category_titles[self.category]} - {self.get_current_command_name()}",
                description=f"현재 페이지: {self.current_page + 1}/{len(self.images[self.category])}",
                color=self.get_category_color()
            )
            embed.set_image(url="attachment://manual.png")
            embed.set_footer(text="버튼을 눌러 페이지를 넘기거나 카테고리를 변경할 수 있는 것이다.")

            # 버튼 상태 업데이트
            self.update_buttons()

            # 이 부분을 수정: attachments=[file] → file=file
            await interaction.response.edit_message(file=file, embed=embed, view=self)
        else:
            await interaction.response.edit_message(content=f"❌ 이미지 파일을 찾을 수 없는 것이다: {file_path}", view=self)

    def get_category_color(self):
        """카테고리에 따른 색상 반환"""
        colors = {
            "user": disnake.Color.blue(),
            "admin": disnake.Color.red(),
            "first": disnake.Color.gold()
        }
        return colors.get(self.category, disnake.Color.default())

    @disnake.ui.button(label="이전", style=disnake.ButtonStyle.secondary)
    async def previous_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @disnake.ui.button(label="다음", style=disnake.ButtonStyle.secondary)
    async def next_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if self.current_page < len(self.images[self.category]) - 1:
            self.current_page += 1
            await self.update_message(interaction)

    @disnake.ui.button(label="일반 명령어", style=disnake.ButtonStyle.primary)
    async def user_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.category = "user"
        self.current_page = 0
        await self.update_message(interaction)

    @disnake.ui.button(label="관리자 명령어", style=disnake.ButtonStyle.danger)
    async def admin_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.category = "admin"
        self.current_page = 0
        await self.update_message(interaction)

    @disnake.ui.button(label="1등 명령어", style=disnake.ButtonStyle.success)
    async def first_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.category = "first"
        self.current_page = 0
        await self.update_message(interaction)

@bot.slash_command(name="메뉴얼", description="챗집봇의 명령어 사용법을 이미지로 보여주는 것이다.")
async def 메뉴얼(inter: disnake.ApplicationCommandInteraction):
    # 응답 지연
    await inter.response.defer()

    view = ManualView()

    # 초기 이미지 및 임베드 설정
    file_path = view.get_current_file_path()

    if file_path and os.path.exists(file_path):
        # 이미지를 파일로 첨부
        file = disnake.File(file_path, filename="manual.png")

        # 임베드 생성
        embed = disnake.Embed(
            title=f"{view.category_titles[view.category]} - {view.get_current_command_name()}",
            description=f"현재 페이지: {view.current_page + 1}/{len(view.images[view.category])}",
            color=view.get_category_color()
        )
        embed.set_image(url="attachment://manual.png")
        embed.set_footer(text="버튼을 눌러 페이지를 넘기거나 카테고리를 변경할 수 있는 것이다.")

        # 버튼 상태 업데이트
        view.update_buttons()

        await inter.followup.send(file=file, embed=embed, view=view)
    else:
        # 이미지 파일을 찾을 수 없는 경우
        await inter.followup.send(
            f"❌ 이미지 파일을 찾을 수 없는 것이다: {file_path}\n"
            f"**중요:** 메뉴얼 이미지를 봇 파일과 같은 위치에 있는 `manual` 폴더 안에 넣어주세요.",
            ephemeral=True
        )
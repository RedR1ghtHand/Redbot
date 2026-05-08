import disnake as discord
from disnake import Interaction, ui

from database.models import Member

from .messages import button_label, modal_text
from .modals import (
    RenameModal,
    SetLimitModal,
    creator_display_label,
    creator_user_id,
)


class ChannelControlView(ui.View):
    def __init__(
        self,
        channel,
        owner,
        session_manager,
        creator_record: Member | None = None,
    ):
        super().__init__(timeout=None)
        self.channel = channel
        self.owner = owner
        self.session_manager = session_manager
        self.creator_record = creator_record

    def _creator_uid(self) -> int | None:
        return creator_user_id(self.owner, self.creator_record)

    @ui.button(label=button_label("buttons.rename.label"), style=discord.ButtonStyle.primary, custom_id="rename_channel")
    async def rename_button(self, button: ui.Button, interaction: Interaction):
        await interaction.response.send_modal(
            RenameModal(
                self.channel,
                self.owner,
                self.session_manager,
                self.creator_record,
            )
        )

    @ui.button(label=button_label("buttons.increase_limit.label"), style=discord.ButtonStyle.success, custom_id="increase_channel_limit")
    async def increase_limit(self, button: ui.Button, interaction: Interaction):
        uid = self._creator_uid()
        if uid is None or interaction.user.id != uid:
            await interaction.response.send_message(
                modal_text(
                    "buttons.increase_limit.msg_error",
                    creator_label=creator_display_label(self.owner, self.creator_record),
                ),
                ephemeral=True,
            )
            return

        new_limit = min((self.channel.user_limit or 0) + 1, 99)
        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            modal_text("buttons.increase_limit.msg_success", new_limit=new_limit),
            ephemeral=True,
        )

    @ui.button(label=button_label("buttons.decrease_limit.label"), style=discord.ButtonStyle.danger, custom_id="decrease_channel_limit")
    async def decrease_limit(self, button: ui.Button, interaction: Interaction):
        uid = self._creator_uid()
        if uid is None or interaction.user.id != uid:
            await interaction.response.send_message(
                modal_text(
                    "buttons.decrease_limit.msg_error",
                    creator_label=creator_display_label(self.owner, self.creator_record),
                ),
                ephemeral=True,
            )
            return

        new_limit = max((self.channel.user_limit or 0) - 1, 1)
        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            modal_text("buttons.decrease_limit.msg_success", new_limit=new_limit),
            ephemeral=True,
        )

    @ui.button(label=button_label("buttons.set_limit.label"), style=discord.ButtonStyle.secondary, custom_id="set_channel_limit")
    async def set_limit_modal(self, button: ui.Button, interaction: Interaction):
        await interaction.response.send_modal(
            SetLimitModal(self.channel, self.owner, self.creator_record)
        )

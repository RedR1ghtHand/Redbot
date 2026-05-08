import disnake as discord
from disnake import Interaction, TextInputStyle, ui

from database.models import Member

from .messages import modal_text


def creator_user_id(owner: discord.Member | None, creator_record: Member | None) -> int | None:
    if owner is not None:
        return owner.id
    if creator_record is not None:
        return creator_record.member_id
    return None


def creator_display_label(owner: discord.Member | None, creator_record: Member | None) -> str:
    if owner is not None:
        return owner.display_name
    if creator_record is not None:
        return creator_record.public_name
    return "the channel owner"


class RenameModal(ui.Modal):
    def __init__(self, channel, owner, session_manager, creator_record: Member | None = None):
        super().__init__(title=modal_text("modals.rename.title"))
        self.channel = channel
        self.owner = owner
        self.session_manager = session_manager
        self.creator_record = creator_record

        self.name_input = ui.TextInput(
            label=modal_text("modals.rename.name_label"),
            placeholder=modal_text("modals.rename.name_placeholder"),
            max_length=33,
            style=TextInputStyle.short,
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: Interaction):
        uid = creator_user_id(self.owner, self.creator_record)
        if uid is None or interaction.user.id != uid:
            await interaction.response.send_message(
                modal_text(
                    "modals.rename.msg_error_owner",
                    creator_label=creator_display_label(self.owner, self.creator_record),
                ),
                ephemeral=True,
            )
            return

        new_name = self.name_input.value.strip()
        if not new_name:
            await interaction.response.send_message(
                modal_text("modals.rename.msg_error_empty"),
                ephemeral=True,
            )
            return

        await self.channel.edit(name=new_name)
        await self.session_manager.update_channel_name(self.channel.id, new_name)
        await interaction.response.send_message(
            modal_text("modals.rename.msg_success", new_name=new_name),
            ephemeral=True,
        )


class SetLimitModal(ui.Modal):
    def __init__(self, channel, owner, creator_record: Member | None = None):
        super().__init__(title=modal_text("modals.set_limit.title"))
        self.channel = channel
        self.owner = owner
        self.creator_record = creator_record

        self.limit_input = ui.TextInput(
            label=modal_text("modals.set_limit.limit_label"),
            placeholder=modal_text("modals.set_limit.limit_placeholder"),
            style=TextInputStyle.short,
            max_length=2,
        )
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: Interaction):
        uid = creator_user_id(self.owner, self.creator_record)
        if uid is None or interaction.user.id != uid:
            await interaction.response.send_message(
                modal_text(
                    "modals.set_limit.msg_error_owner",
                    creator_label=creator_display_label(self.owner, self.creator_record),
                ),
                ephemeral=True,
            )
            return

        try:
            new_limit = int(self.limit_input.value)
            if new_limit < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                modal_text("modals.set_limit.msg_error_invalid"),
                ephemeral=True,
            )
            return

        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            modal_text("modals.set_limit.msg_success", new_limit=new_limit),
            ephemeral=True,
        )

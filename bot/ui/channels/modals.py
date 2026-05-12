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
    def __init__(self, channel, owner, session_gateway, creator_record: Member | None = None):
        self.channel = channel
        self.owner = owner
        self.session_gateway = session_gateway
        self.creator_record = creator_record

        self.name_input_custom_id = "rename_channel_name"
        components = [
            ui.Label(
                text=modal_text("modals.rename.name_label"),
                component=ui.TextInput(
                    custom_id=self.name_input_custom_id,
                    placeholder=modal_text("modals.rename.name_placeholder"),
                    max_length=33,
                    style=TextInputStyle.short,
                ),
            )
        ]
        super().__init__(
            title=modal_text("modals.rename.title"),
            components=components,
        )

    async def callback(self, interaction: Interaction):
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

        new_name = str(interaction.values.get(self.name_input_custom_id, "")).strip()
        if not new_name:
            await interaction.response.send_message(
                modal_text("modals.rename.msg_error_empty"),
                ephemeral=True,
            )
            return

        await self.channel.edit(name=new_name)
        await self.session_gateway.update_channel_name(self.channel.id, new_name)
        await interaction.response.send_message(
            modal_text("modals.rename.msg_success", new_name=new_name),
            ephemeral=True,
        )


class SetLimitModal(ui.Modal):
    def __init__(self, channel, owner, creator_record: Member | None = None):
        self.channel = channel
        self.owner = owner
        self.creator_record = creator_record

        self.limit_input_custom_id = "set_channel_limit_value"
        components = [
            ui.Label(
                text=modal_text("modals.set_limit.limit_label"),
                component=ui.TextInput(
                    custom_id=self.limit_input_custom_id,
                    placeholder=modal_text("modals.set_limit.limit_placeholder"),
                    style=TextInputStyle.short,
                    max_length=2,
                ),
            )
        ]
        super().__init__(
            title=modal_text("modals.set_limit.title"),
            components=components,
        )

    async def callback(self, interaction: Interaction):
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
            new_limit = int(str(interaction.values.get(self.limit_input_custom_id, "")).strip())
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

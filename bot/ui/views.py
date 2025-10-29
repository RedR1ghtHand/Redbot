import discord
from discord import Interaction, ui

from .modals import RenameModal, SetLimitModal


class ChannelControlView(ui.View):
    def __init__(self, channel, owner, session_manager):
        super().__init__(timeout=None)
        self.channel = channel
        self.owner = owner
        self.session_manager = session_manager

    @ui.button(label="📝", style=discord.ButtonStyle.primary)
    async def rename_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(RenameModal(self.channel, self.owner, self.session_manager))

    @ui.button(label="👥+", style=discord.ButtonStyle.success)
    async def increase_limit(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the channel owner can change the limit!", ephemeral=True
            )
            return

        new_limit = (self.channel.user_limit or 0) + 1
        if new_limit > 99:
            new_limit = 99

        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            f"Channel limit increased to {new_limit}.", ephemeral=True
        )

    @ui.button(label="👥-", style=discord.ButtonStyle.danger)
    async def decrease_limit(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the channel owner can change the limit!", ephemeral=True
            )
            return

        new_limit = (self.channel.user_limit or 0) - 1
        if new_limit < 1:
            new_limit = 1

        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            f"Channel limit decreased to {new_limit}.", ephemeral=True
        )

    @ui.button(label="👥*", style=discord.ButtonStyle.secondary)
    async def set_limit_modal(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(SetLimitModal(self.channel, self.owner))
        
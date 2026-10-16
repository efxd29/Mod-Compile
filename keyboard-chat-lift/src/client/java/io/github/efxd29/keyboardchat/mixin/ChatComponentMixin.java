package io.github.efxd29.keyboardchat.mixin;

import io.github.efxd29.keyboardchat.KeyboardChatOffset;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphicsExtractor;
import net.minecraft.client.gui.components.ChatComponent;
import net.minecraft.client.gui.screens.ChatScreen;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Raises the real vanilla chat by changing its chat-bottom calculation only while ChatScreen is open. */
@Mixin(ChatComponent.class)
public abstract class ChatComponentMixin {
    @Redirect(
        method = "extractRenderState",
        at = @At(
            value = "INVOKE",
            target = "Lnet/minecraft/client/gui/GuiGraphicsExtractor;guiHeight()I"
        )
    )
    private int keyboardchat$raiseVanillaChatBottom(final GuiGraphicsExtractor graphics) {
        final int originalHeight = graphics.guiHeight();
        if (Minecraft.getInstance().gui.screen() instanceof ChatScreen) {
            return originalHeight - KeyboardChatOffset.forGuiHeight(originalHeight);
        }
        return originalHeight;
    }
}

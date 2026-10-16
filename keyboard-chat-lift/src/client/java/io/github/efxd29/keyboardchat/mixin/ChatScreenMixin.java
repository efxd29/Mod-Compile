package io.github.efxd29.keyboardchat.mixin;

import io.github.efxd29.keyboardchat.KeyboardChatOffset;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.ChatScreen;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Moves only the native chat input widget and its background, not the screen or game viewport. */
@Mixin(ChatScreen.class)
public abstract class ChatScreenMixin {
    @Shadow
    protected EditBox input;

    @Inject(method = "init", at = @At("TAIL"))
    private void keyboardchat$raiseInput(final CallbackInfo ci) {
        if (this.input != null) {
            this.input.setY(this.input.getY() - keyboardchat$offset());
        }
    }

    @ModifyArg(
        method = "extractRenderState",
        at = @At(
            value = "INVOKE",
            target = "Lnet/minecraft/client/gui/GuiGraphicsExtractor;fill(IIIII)V",
            ordinal = 0
        ),
        index = 1
    )
    private int keyboardchat$raiseInputBackgroundTop(final int y) {
        return y - keyboardchat$offset();
    }

    @ModifyArg(
        method = "extractRenderState",
        at = @At(
            value = "INVOKE",
            target = "Lnet/minecraft/client/gui/GuiGraphicsExtractor;fill(IIIII)V",
            ordinal = 0
        ),
        index = 3
    )
    private int keyboardchat$raiseInputBackgroundBottom(final int y) {
        return y - keyboardchat$offset();
    }

    private static int keyboardchat$offset() {
        return KeyboardChatOffset.forGuiHeight(Minecraft.getInstance().getWindow().getGuiScaledHeight());
    }
}

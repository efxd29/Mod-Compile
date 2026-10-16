package com.chatmover.mixin;

import com.chatmover.ChatMoverClient;
import net.minecraft.client.gui.hud.ChatHud;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

@Mixin(ChatHud.class)
public class ChatHudMixin {

    // Menggeser Y-offset chat hud secara dinamis berdasarkan tinggi keyboard yang aktif
    @ModifyVariable(
        method = "render",
        at = @At("HEAD"),
        ordinal = 0,
        argsOnly = true
    )
    private int modifyChatY(int originalY) {
        int dynamicOffset = ChatMoverClient.getKeyboardHeight();
        // Jika keyboard muncul, geser ke atas sesuai tinggi pixel keyboard; jika tertutup, kembali normal (0)
        return originalY - dynamicOffset;
    }
}

package dev.efxd29.essentialsfabric;

import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.Permissions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class EssentialsFabric implements ModInitializer {
    private static final String MOD_ID = "essentialsfabric";
    private static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

    @Override
    public void onInitialize() {
        CommandRegistrationCallback.EVENT.register((dispatcher, buildContext, selection) ->
            dispatcher.register(Commands.literal("sudo")
                .requires(source -> source.permissions().hasPermission(Permissions.COMMANDS_ADMIN))
                .then(Commands.argument("target", EntityArgument.player())
                    .then(Commands.argument("command", StringArgumentType.greedyString())
                        .executes(context -> executeSudo(
                            context.getSource(),
                            EntityArgument.getPlayer(context, "target"),
                            StringArgumentType.getString(context, "command")
                        ))
                    )
                )
            )
        );

        LOGGER.info("Essentials Fabric (sudo) initialized for Minecraft 26.3.");
    }

    private static int executeSudo(CommandSourceStack source, ServerPlayer target, String rawCommand) {
        String command = normalizeCommand(rawCommand);
        if (command.isEmpty()) {
            source.sendFailure(Component.literal("Usage: /sudo <player> <command>"));
            return 0;
        }

        // Use a source created from the target, preserving the target's permissions and player context.
        target.getServer().getCommands().performPrefixedCommand(
            target.createCommandSourceStack(),
            command
        );

        String targetName = target.getName().getString();
        LOGGER.info("Sudo issued by '{}' as '{}': /{}", source.getTextName(), targetName, command);
        source.sendSuccess(
            () -> Component.literal("Sent /" + command + " as " + targetName + "."),
            false
        );
        return 1;
    }

    private static String normalizeCommand(String command) {
        String normalized = command == null ? "" : command.strip();
        if (normalized.startsWith("/")) {
            normalized = normalized.substring(1).stripLeading();
        }
        return normalized;
    }
}

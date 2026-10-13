from pathlib import Path
import json
import re
import sys

BUILD_ROOT = Path(sys.argv[1])
ROOT = BUILD_ROOT / 'src/main/java/dev/dragonfirst/DragonFirstState.java'
s = ROOT.read_text()
s = s.replace('import net.minecraft.world.entity.EntityType;', 'import net.minecraft.world.entity.EntityTypes;')
s = s.replace('EntityType.END_CRYSTAL', 'EntityTypes.END_CRYSTAL')

def rep(old, new, label):
    global s
    count = s.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one match, found {count}')
    s = s.replace(old, new)

rep('    private static boolean firstWinSpawnResetApplied;\n    private static Encounter encounter = Encounter.NONE;\n',
    '    private static boolean firstWinSpawnResetApplied;\n    private static boolean firstWinTowerCrystalsApplied;\n    private static final Map<UUID, Boolean> lastPortalPermission = new HashMap<>();\n    private static Encounter encounter = Encounter.NONE;\n',
    'add state fields')

rep('        firstWinSpawnResetApplied = false;\n        DragonFirstMod.LOGGER.info("DragonFirst state loaded:',
    '        firstWinSpawnResetApplied = false;\n        firstWinTowerCrystalsApplied = false;\n        lastPortalPermission.clear();\n        DragonFirstMod.LOGGER.info("DragonFirst state loaded:',
    'reset transient state')

rep('        } else if (encounter != Encounter.FIRST_WIN) {\n            firstWinSpawnResetApplied = false;\n        }\n\n        if (encounter != Encounter.NONE) {',
    '        } else if (encounter != Encounter.FIRST_WIN) {\n            firstWinSpawnResetApplied = false;\n        }\n\n        // Restore the ten vanilla pillar crystals as soon as the first-win dragon exists.\n        if (encounter == Encounter.FIRST_WIN && !end.getDragons().isEmpty()\n                && !firstWinTowerCrystalsApplied) {\n            ensureTowerCrystals(end);\n            firstWinTowerCrystalsApplied = true;\n        } else if (encounter != Encounter.FIRST_WIN) {\n            firstWinTowerCrystalsApplied = false;\n        }\n\n        if (encounter != Encounter.NONE) {',
    'trigger 10 tower crystals')

rep('        ensureFirstWinCrystals(end);\n', '', 'remove temporary pair of crystals')

start = '    /** Add two encounter crystals off the four cardinal ritual positions used by vanilla. */\n'
end = '    public static void finishEncounter(EnderDragon dragon) {\n'
if s.count(start) != 1 or s.count(end) != 1:
    raise RuntimeError(f'crystal method region mismatch: start={s.count(start)} end={s.count(end)}')
a = s.index(start)
b = s.index(end, a)
replacement = '''    /** Restore the ten End-spike crystals for a player's first-win encounter. */
    private static void ensureTowerCrystals(ServerLevel end) {
        BlockPos center = EnderDragonFight.getPodiumLocation(BlockPos.ZERO);
        int found = 0;
        int created = 0;
        for (int i = 0; i < 10; i++) {
            // Matches the fixed radius and angular spacing used by vanilla End spikes.
            double angle = -2.0D * Math.PI + (double) i * Math.PI / 5.0D;
            int expectedX = center.getX() + (int) Math.floor(42.0D * Math.cos(angle));
            int expectedZ = center.getZ() + (int) Math.floor(42.0D * Math.sin(angle));
            BlockPos top = findTowerTop(end, expectedX, expectedZ);
            if (top == null) {
                DragonFirstMod.LOGGER.warn("Could not locate End spike {} near {}, {}; skipping its crystal.", i, expectedX, expectedZ);
                continue;
            }
            found++;
            if (ensureTowerCrystal(end, top)) created++;
        }
        DragonFirstMod.LOGGER.info("First-win dragon tower crystals checked: {} of 10 pillars found; {} crystal(s) restored.", found, created);
    }

    private static BlockPos findTowerTop(ServerLevel end, int expectedX, int expectedZ) {
        BlockPos best = null;
        int bestY = Integer.MIN_VALUE;
        int bestDistance = Integer.MAX_VALUE;
        // Each vanilla pillar is wide enough that a small center search tolerates rounding
        // differences without accidentally selecting the neighboring pillar.
        for (int dx = -5; dx <= 5; dx++) {
            for (int dz = -5; dz <= 5; dz++) {
                int x = expectedX + dx;
                int z = expectedZ + dz;
                for (int y = 120; y >= 64; y--) {
                    BlockPos pos = new BlockPos(x, y, z);
                    BlockState state = end.getBlockState(pos);
                    if (!(state.is(Blocks.OBSIDIAN) || state.is(Blocks.BEDROCK))) continue;
                    BlockState above = end.getBlockState(pos.above());
                    if (above.is(Blocks.OBSIDIAN) || above.is(Blocks.BEDROCK)) continue;
                    int distance = dx * dx + dz * dz;
                    if (y > bestY || (y == bestY && distance < bestDistance)) {
                        best = pos.immutable();
                        bestY = y;
                        bestDistance = distance;
                    }
                    break;
                }
            }
        }
        return best;
    }

    private static boolean ensureTowerCrystal(ServerLevel end, BlockPos top) {
        double x = top.getX() + 0.5D;
        double y = top.getY() + 1.0D;
        double z = top.getZ() + 0.5D;
        AABB search = new AABB(x - 1.25D, y - 0.5D, z - 1.25D,
                x + 1.25D, y + 2.5D, z + 1.25D);
        for (EndCrystal existing : end.getEntitiesOfClass(EndCrystal.class, search)) {
            if (existing.distanceToSqr(x, y, z) < 2.25D) return false;
        }
        EndCrystal crystal = EntityTypes.END_CRYSTAL.create(end, EntitySpawnReason.TRIGGERED);
        if (crystal == null) {
            DragonFirstMod.LOGGER.warn("Could not create an End Crystal at pillar {}, {}, {}.", top.getX(), top.getY(), top.getZ());
            return false;
        }
        crystal.setPos(x, y, z);
        if (!end.addFreshEntity(crystal)) {
            DragonFirstMod.LOGGER.warn("Could not add an End Crystal at pillar {}, {}, {}.", top.getX(), top.getY(), top.getZ());
            return false;
        }
        return true;
    }

'''
s = s[:a] + replacement + s[b:]

rep('''                firstWins.add(id);
                ServerPlayer player = level.getServer().getPlayerList().getPlayer(id);
                if (!alreadyHadFirstWin && player != null) awardFirstWinAdvancement(level.getServer(), player);''',
    '''                firstWins.add(id);
                // A first-win encounter is a valid completed dragon kill for these players,
                // even if the shared world has seen several earlier respawn rituals.
                completedRespawn.put(id, respawnSerial);
                ServerPlayer player = level.getServer().getPlayerList().getPlayer(id);
                if (!alreadyHadFirstWin && player != null) awardFirstWinAdvancement(level.getServer(), player);''',
    'unlock portal after first win')

rep('''        for (ServerPlayer player : players) {
            BlockState desired = canUsePortal(player) ? activePortal : hidden;
            for (BlockPos pos : portalBlocks) {
                if (!end.getBlockState(pos).equals(desired)) {
                    player.connection.send(new ClientboundBlockUpdatePacket(pos, desired));
                }
            }
        }''',
    '''        for (ServerPlayer player : players) {
            boolean allowed = canUsePortal(player);
            Boolean previous = lastPortalPermission.put(player.getUUID(), allowed);
            // The real End portal can already exist in the world, while this player still has
            // a client-side AIR view cached from their locked period. Force a refresh when
            // the per-player permission flips, even when the server block already matches.
            boolean permissionChanged = previous == null || previous.booleanValue() != allowed;
            BlockState desired = allowed ? activePortal : hidden;
            for (BlockPos pos : portalBlocks) {
                if (permissionChanged || !end.getBlockState(pos).equals(desired)) {
                    player.connection.send(new ClientboundBlockUpdatePacket(pos, desired));
                }
            }
        }''',
    'refresh per-player portal block view')

rep('''        for (ServerPlayer player : players) {
            if (!canUsePortal(player)) continue;
            for (BlockPos pos : portalBlocks) {
                double dx = player.getX() - (pos.getX() + 0.5D);
                double dz = player.getZ() - (pos.getZ() + 0.5D);
                double dy = player.getY() - (pos.getY() + 1.0D);
                if (Math.abs(dx) > 0.48D || Math.abs(dz) > 0.48D || dy < -0.25D || dy > 2.0D) continue;
                if (end.getBlockState(pos).is(Blocks.END_PORTAL)) continue;
                try {''',
    '''        for (ServerPlayer player : players) {
            if (player.level() != end || !canUsePortal(player)) continue;
            for (BlockPos pos : portalBlocks) {
                // Real END_PORTAL blocks use vanilla's normal entity-inside handling.
                if (end.getBlockState(pos).is(Blocks.END_PORTAL)) continue;
                AABB portalBox = new AABB(pos.getX(), pos.getY(), pos.getZ(),
                        pos.getX() + 1.0D, pos.getY() + 1.0D, pos.getZ() + 1.0D);
                // For virtual portal cells, require actual bounding-box intersection with the
                // one-block portal volume; standing on the bedrock rim above cannot trigger it.
                if (!player.getBoundingBox().intersects(portalBox)) continue;
                try {''',
    'portal touch fallback')

# Preserve the virtual portal fallback only for a true block/entity AABB intersection.
# It is needed for tracked portal cells that are virtual AIR on the server, while real
# END_PORTAL blocks still rely on vanilla's own entity-inside method.
if 'import net.minecraft.world.phys.AABB;' not in s:
    import_anchor = 'import net.minecraft.world.level.block.state.BlockState;\n'
    if s.count(import_anchor) != 1:
        raise RuntimeError('could not find BlockState import to add AABB import')
    s = s.replace(import_anchor, import_anchor + 'import net.minecraft.world.phys.AABB;\n')

# Begin distinguishing the actual dragon-spawn moment from the encounter flag.
# Player-placed blocks are protected if they were placed before the dragon entity exists,
# even when the mod had already prepared the first-win encounter.
old_record = '''        if (level.dimension().equals(Level.END) && encounter == Encounter.FIRST_WIN
                && newlyPlacedBlocks.add(pos.immutable())) markDirty();'''
new_record = '''        if (level.dimension().equals(Level.END) && encounter == Encounter.FIRST_WIN
                && !level.getDragons().isEmpty()
                && newlyPlacedBlocks.add(pos.immutable())) markDirty();'''
if s.count(old_record) != 1:
    raise RuntimeError(f'recordPlacedBlock predicate: expected one match, found {s.count(old_record)}')
s = s.replace(old_record, new_record)

ROOT.write_text(s)
props = BUILD_ROOT / 'gradle.properties'
props_text = props.read_text()
props_text, count = re.subn(r'^version=.*$', 'version=1.0-f', props_text, count=1, flags=re.MULTILINE)
if count != 1:
    raise RuntimeError('Could not set mod version to 1.0-f')
props.write_text(props_text)
mixins_path = BUILD_ROOT / 'src/main/resources/dragonfirst.mixins.json'
mixins = json.loads(mixins_path.read_text())
mixins['mixins'] = [name for name in mixins.get('mixins', []) if name != 'BlockStateCollisionMixin']
mixins_path.write_text(json.dumps(mixins, indent=2) + '\n')
(BUILD_ROOT / 'src/main/java/dev/dragonfirst/mixin/BlockStateCollisionMixin.java').unlink(missing_ok=True)
print('Patched first-win crystals, per-player portal unlock/sync, and version 1.0-f:', BUILD_ROOT)

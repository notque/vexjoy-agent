# Phaser Error Handling

Verbatim error matrix for common Phaser 3 issues.

### "Spritesheet frame dimensions wrong / animation looks corrupt"
Cause: `frameWidth` or `frameHeight` does not match the actual PNG.
Fix: Open the spritesheet in an image editor. Count total pixel width ÷ columns = frameWidth. Total height ÷ rows = frameHeight. Never estimate. See `references/spritesheets.md`.

### "Cannot read properties of undefined (reading 'body')"
Cause: Accessing a physics body before `create()` completes, or on a non-physics sprite.
Fix: Only use `.body` on sprites created via `this.physics.add.sprite()` or `this.physics.add.existing()`. Static images do not have bodies.

### "Tilemap layer collision has no effect"
Cause: Missing `setCollisionByProperty` or property name mismatch in Tiled.
Fix: In Tiled, verify the tile property is named exactly `collides` (boolean true). Call `layer.setCollisionByProperty({ collides: true })`. See `references/tilemaps.md`.

### "Physics bodies not colliding"
Cause: `this.physics.add.collider()` called before both objects exist, or wrong group types.
Fix: Call all collider setup at the end of `create()`, after all sprites and groups are created.

### "Animation not playing"
Cause: Animation key typo, `anims.create()` called before texture is loaded, or wrong frame range.
Fix: Animations must be defined in `create()`, not `preload()`. Verify key strings match exactly between `anims.create({ key: 'walk' })` and `sprite.play('walk')`.

### "Game runs slow on mobile"
Cause: Too many active physics bodies, continuously emitting particles, or per-frame allocations.
Fix: Pool bullets and enemies (see `references/performance.md`). Set emitters to `emitting: false` and call `explode()` on demand. Display `game.loop.actualFps` to profile.

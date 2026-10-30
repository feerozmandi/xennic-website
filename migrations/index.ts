import * as migration_20261030_163225_baseline from './20261030_163225_baseline';

export const migrations = [
  {
    up: migration_20261030_163225_baseline.up,
    down: migration_20261030_163225_baseline.down,
    name: '20261030_163225_baseline'
  },
];

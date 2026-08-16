import { PassThrough } from 'node:stream'
import { describe, expect, it, vi } from 'vitest'
import { spawnSubprocess, taskkillProcessTree } from '../src/spawn.ts'

const { spawnMock, spawnSyncMock } = vi.hoisted(() => ({
  spawnMock: vi.fn(),
  spawnSyncMock: vi.fn(),
}))

vi.mock('node:child_process', () => ({
  spawn: spawnMock,
  spawnSync: spawnSyncMock,
}))

describe('windows console hiding', () => {
  it('spawns children with windowsHide: true', () => {
    spawnMock.mockReturnValueOnce({
      pid: 12345,
      stdout: new PassThrough(),
      stderr: new PassThrough(),
      stdin: null,
      exitCode: null,
      signalCode: null,
      on: vi.fn(),
      kill: vi.fn(),
    })
    spawnSubprocess({
      argv: ['node', '-e', ''],
      cwd: process.cwd(),
      stdio: {
        stdin: 'ignore',
        stdout: { maxBytes: 1000, spill: { maxBytes: 1000 } },
        stderr: { maxBytes: 1000, spill: { maxBytes: 1000 } },
      },
      graceMs: 3000,
    })
    expect(spawnMock).toHaveBeenCalledWith(
      'node',
      ['-e', ''],
      expect.objectContaining({ windowsHide: true }),
    )
  })

  it('hides the taskkill console window', () => {
    spawnSyncMock.mockReturnValueOnce({ status: 0 })
    taskkillProcessTree(12345)
    expect(spawnSyncMock).toHaveBeenCalledWith(
      'taskkill',
      ['/PID', '12345', '/T', '/F'],
      expect.objectContaining({ windowsHide: true }),
    )
  })
})

# 网易盾无感验证码实现说明

目录：`analysis/dun_sense/`

目标站点：`https://dun.163.com/trial/sense`

当前结论：这个目录已经有一套可复用实现，核心入口是 `scripts/step5_check.py`。其余 `scripts/step2/3/4` 是分阶段验证脚本，原始 SDK 包保留为参考材料，不参与日常运行。

## 一、当前状态

| 步骤 | 接口 | 状态 | 主要文件 |
|------|------|------|----------|
| Step 1 | `/v4/j/c` | 可选 | `scripts/step1_ir_sdk_config.py` |
| Step 2 | `/api/v2/getconf` | 可用 | `scripts/step2_getconf.py` |
| Step 3 | `/v4/j/up` | 可用 | `scripts/step3_up.py`, `encoders/env.js` |
| Step 4 | `/api/v3/get` | 可用 | `scripts/step4_get.py`, `encoders/fp_encoder.js`, `encoders/cb_encoder.js` |
| Step 5 | `/api/v3/check` | 可用 | `scripts/step5_check.py`, `encoders/data_encoder.js` |

## 二、真正要保留的主件

### 运行主件

- `scripts/step5_check.py`
  完整流程入口，内部已整合 step2 -> step5。
- `scripts/step4_get.py`
  用于单独验证 `get` 阶段，定位 `fp` / `cb` 是否失效。
- `scripts/step3_up.py`
  用于单独验证 `env.js` 生成的 `d/n` 是否仍有效。
- `scripts/step2_getconf.py`
  用于单独验证配置接口是否正常。
- `scripts/step1_ir_sdk_config.py`
  可选参考脚本，非主流程必需。

### 参数实现

- `encoders/env.js`
  生成 `/v4/j/up` 所需 `d` 和 `n`。
- `encoders/fp_encoder.js`
  生成 `/api/v3/get` 所需 `fp`。
- `encoders/cb_encoder.js`
  生成 `/api/v3/get` 和 `/api/v3/check` 所需 `cb`。
- `encoders/data_encoder.js`
  生成 `/api/v3/check` 所需 `data.d/m/p/ext`。

## 三、参考材料

下面这些文件用于回溯常量、版本和加密逻辑来源，不是日常运行入口：

- `samples/core-optimi.min.js`
- `samples/ir.2.0.13.min.js`
- `samples/neguardian.umd.js`

建议把它们视为“参考样本”，只有在参数失效、需要重新提取常量时才去看。

## 四、请求链路

```text
1. /api/v2/getconf
   -> 返回 dt、zoneId、ir.pn

2. /v4/j/up
   -> 用 env.js 生成 d/n
   -> 返回 irToken

3. /api/v3/get
   -> 用 fp_encoder.js 生成 fp
   -> 用 cb_encoder.js 生成 cb
   -> 返回 token

4. /api/v3/check
   -> 用 cb_encoder.js 生成 cb
   -> 用 data_encoder.js 生成 data
   -> 返回 result / validate
```

## 五、故障定位建议

按最小失败域拆开排查，不要一上来全改。

### `step3_up.py` 失败

优先怀疑：

- `encoders/env.js`
- `/v4/j/up` 请求头或载荷格式

### `step4_get.py` 失败

优先怀疑：

- `encoders/fp_encoder.js`
- `encoders/cb_encoder.js`
- `dt / zoneId / irToken` 已失效

### `step5_check.py` 失败，但 `step4_get.py` 成功

优先怀疑：

- `encoders/data_encoder.js`
- 轨迹和点击数据构造
- `encoders/cb_encoder.js` 常量版本漂移

## 六、推荐使用顺序

### 日常验证

```text
先跑 scripts/step5_check.py
```

### 分阶段排障

```text
scripts/step2_getconf.py
-> scripts/step3_up.py
-> scripts/step4_get.py
-> scripts/step5_check.py
```

## 七、整理后的目录意图

```text
analysis/dun_sense/
├── docs/
│   └── flow.md
├── encoders/
│   ├── env.js
│   ├── fp_encoder.js
│   ├── cb_encoder.js
│   └── data_encoder.js
├── scripts/
│   ├── step1_ir_sdk_config.py
│   ├── step2_getconf.py
│   ├── step3_up.py
│   ├── step4_get.py
│   └── step5_check.py
└── samples/
    ├── core-optimi.min.js
    ├── ir.2.0.13.min.js
    └── neguardian.umd.js
```

## 八、这次整理做了什么

- 删除了临时分析脚本和一次性测试脚本
- 保留了分阶段验证入口，方便定位失效点
- 把“可运行实现”和“参考原始包”明确分开
- 把入口文档收敛到当前真实状态

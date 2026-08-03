# 小模型→大模型输出分布代理与数据集质量分析

## 定位

该模块不是“让小模型神奇地知道大模型答案”，而是一个可校准的教师输出代理：

1. 小模型保存完整类别概率分布，而不只保存 argmax 和置信度。
2. 有真实大模型配对输出时，学习平滑的类别转移矩阵。
3. 没有配对输出时仅输出“未校准代理”，界面与 API 不得称其为真实大模型结果。
4. 用大小模型分歧辅助找问题，但不自动删除样本。

## 输入约定

小模型输出写入 `FrameAnnotation.assist_metadata.phase_probabilities`（兼容
`student_distribution`）。真实大模型分布可写入：

```json
{
  "teacher_distribution": {
    "preparation": 0.03,
    "backswing": 0.08,
    "contact": 0.78,
    "follow_through": 0.09,
    "recovery": 0.02
  }
}
```

至少需要 10 条且每类约 2 条配对数据后，系统才标记为 `calibrated`。配对样本仍应覆盖
不同比赛、选手、机位、遮挡程度，不能只抽最容易的帧。

## 质量信号

- `model_gap`：小模型和教师/教师代理分布的 Jensen–Shannon 分歧。
- `label_conflict`：人工阶段标签在教师分布下的冲突程度。
- `temporal_jump`：同一人物相邻帧输出分布的不合理跳变。
- `redundancy`：抽帧新颖度低，且模型低熵时可能是低信息重复样本。
- `entropy`：高熵表示困难或信息量高，不能单独当作坏数据。

质量风险用于生成复核队列；“难样本”“错标”“域外样本”和“重复样本”必须分开统计。
API：`GET /tasks/{batch_id}/teacher-surrogate-quality`。

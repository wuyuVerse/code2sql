# Tested successfully on the hiyouga/verl:ngc-th2.6.0-cu126-vllm0.8.4-flashinfer0.2.2-cxx11abi0 image.
# It outperforms the Qwen2 7B base model by two percentage points on the test set of GSM8K.
export PYTHONPATH="/data/cloud_disk_1/home/wuyu/code2sql/verl-main:$PYTHONPATH"

export GLOO_SOCKET_IFNAME=eth0
export NCCL_SOCKET_IFNAME=eth0
export NCCL_IB_DISABLE=1
export GLOO_SOCKET_FAMILY=AF_INET
export NCCL_DEBUG=INFO



# 创建日志目录
LOG_DIR="/data/cloud_disk_1/home/wuyu/code2sql/logs"
mkdir -p ${LOG_DIR}

# 生成带时间戳的日志文件名
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOG_DIR}/grpo_qwen3_32b_${TIMESTAMP}.log"

echo "训练开始时间: $(date)"
echo "日志文件: ${LOG_FILE}"

set -x

# 运行训练并在后台运行
nohup python3 -m verl.trainer.main_ppo \
    algorithm.adv_estimator=reinforce_plus_plus \
    data.train_files=/data/cloud_disk_1/home/wuyu/code2sql/verl_train_dataset_train_no_think.parquet \
    data.val_files=/data/cloud_disk_1/home/wuyu/code2sql/verl_train_dataset_val_no_think.parquet \
    data.train_batch_size=64 \
    data.max_prompt_length=8192 \
    data.max_response_length=4096 \
    data.filter_overlong_prompts=True \
    data.truncation='left' \
    data.trust_remote_code=True \
    actor_rollout_ref.model.path=/data/cloud_disk_1/home/wuyu/code2sql/models/Qwen3-32B \
    actor_rollout_ref.model.enable_gradient_checkpointing=True \
    actor_rollout_ref.model.trust_remote_code=True \
    actor_rollout_ref.actor.optim.lr=3e-6 \
    actor_rollout_ref.model.use_remove_padding=True \
    actor_rollout_ref.actor.ppo_mini_batch_size=64 \
    actor_rollout_ref.actor.clip_ratio_low=0.2 \
    actor_rollout_ref.actor.clip_ratio_high=0.28 \
    actor_rollout_ref.actor.use_dynamic_bsz=True \
    actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=2 \
    actor_rollout_ref.actor.use_kl_loss=True \
    actor_rollout_ref.actor.kl_loss_coef=0.001 \
    actor_rollout_ref.actor.kl_loss_type=low_var_kl \
    actor_rollout_ref.actor.entropy_coeff=0.001 \
    actor_rollout_ref.actor.fsdp_config.param_offload=False \
    actor_rollout_ref.actor.fsdp_config.optimizer_offload=False \
    actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu=1 \
    actor_rollout_ref.rollout.tensor_model_parallel_size=4 \
    actor_rollout_ref.rollout.name=vllm \
    actor_rollout_ref.rollout.gpu_memory_utilization=0.9 \
    actor_rollout_ref.rollout.n=1 \
    actor_rollout_ref.rollout.enable_chunked_prefill=False \
    actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu=1 \
    actor_rollout_ref.ref.fsdp_config.param_offload=True \
    reward_model.reward_manager=batch \
    algorithm.use_kl_in_reward=False \
    custom_reward_function.path=/data/cloud_disk_1/home/wuyu/code2sql/verl-main/reward_lib/composite_reward.py \
    custom_reward_function.name=compute_score_batch \
    trainer.critic_warmup=0 \
    trainer.logger=['console','swanlab'] \
    trainer.project_name='verl_reinforce_plus_plus_formal' \
    trainer.experiment_name='qwen3_32b_rl-0704-reinforce-plus-plus' \
    trainer.n_gpus_per_node=8 \
    trainer.nnodes=4 \
    trainer.save_freq=20 \
    trainer.test_freq=5 \
    trainer.total_epochs=20 \
    > "${LOG_FILE}" 2>&1 &

# 获取后台进程的PID
TRAIN_PID=$!
echo "训练进程PID: ${TRAIN_PID}"
echo "训练进程在后台运行，日志文件: ${LOG_FILE}"

# 等待训练完成
wait ${TRAIN_PID}

echo "训练结束时间: $(date)"
echo "日志保存在: ${LOG_FILE}"
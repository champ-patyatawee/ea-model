# deploy_pod — RL training on RunPod (8 vCPU CPU pod)

Everything the pod needs. Data CSVs are gitignored; only code + real M1 is here.

## Layout
```
deploy_pod/
  setup.sh            # create venv, install deps, place files
  run.sh              # regenerate synthetic data -> launch Phase-2 training
  gen_real_synth.py   # realistic synthetic generator (block-bootstrap)
  run_phase2.py       # sliding walk-forward PPO training (n_envs=8)
  src/                # same scripts (source copies)
  vendor/             # Reinforcement_Trading_Part_2 (no .git/__pycache__)
  data/xauusdm_m1.csv # real XAUUSDm M1 (34 MB) -- git-LFS recommended
```

## On a fresh pod
```bash
# 1. get this folder onto the pod (git clone or scp)
cd /root && git clone <this-repo> deploy_pod_repo
mv deploy_pod_repo/deploy_pod /root/deploy_pod

# 2. install
bash /root/deploy_pod/setup.sh

# 3. synthetic + train (background)
bash /root/deploy_pod/run.sh

# 4. watch
tail -f /root/rl_gold/phase2.log
```

## Outputs
```
/root/rl_gold/models_phase2/sliding_walk_forward_summary.csv   # per-fold OOS
/root/rl_gold/models_phase2/sliding_oos_equity.csv             # stitched OOS
/root/rl_gold/models_phase2/best_model/best_model.zip          # deployable
```

## Notes
- Container disk is ephemeral: re-run setup.sh after every pod restart.
- 8 vCPU -> `n_envs=8`. Wall clock for 9 folds x 200k steps ~ 40-70 min.
- Then Phase 3: backtest on REAL Jul-Sep 2026 (sealed) before any demo.

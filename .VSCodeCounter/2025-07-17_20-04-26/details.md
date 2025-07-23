# Details

Date : 2025-07-17 20:04:26

Directory /home/wuyu/code2sql

Total : 74 files,  21876 codes, 0 comments, 4304 blanks, all 26180 lines

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [config/__init__.py](/config/__init__.py) | Python | 3 | 0 | 1 | 4 |
| [config/data_processing/__init__.py](/config/data_processing/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [config/data_processing/cleaning/fix_review_prompts.py](/config/data_processing/cleaning/fix_review_prompts.py) | Python | 59 | 0 | 30 | 89 |
| [config/data_processing/cleaning/keyword_processing_prompt.py](/config/data_processing/cleaning/keyword_processing_prompt.py) | Python | 146 | 0 | 34 | 180 |
| [config/data_processing/cleaning/special_keyword_prompt.py](/config/data_processing/cleaning/special_keyword_prompt.py) | Python | 124 | 0 | 23 | 147 |
| [config/data_processing/cleaning/sql_completeness_check_prompt.py](/config/data_processing/cleaning/sql_completeness_check_prompt.py) | Python | 133 | 0 | 31 | 164 |
| [config/data_processing/synthetic_data_generator/__init__.py](/config/data_processing/synthetic_data_generator/__init__.py) | Python | 12 | 0 | 3 | 15 |
| [config/data_processing/synthetic_data_generator/config.py](/config/data_processing/synthetic_data_generator/config.py) | Python | 197 | 0 | 44 | 241 |
| [config/data_processing/synthetic_data_generator/prompts.py](/config/data_processing/synthetic_data_generator/prompts.py) | Python | 87 | 0 | 19 | 106 |
| [config/data_processing/validation/control_flow_validation_prompt.py](/config/data_processing/validation/control_flow_validation_prompt.py) | Python | 175 | 0 | 38 | 213 |
| [config/data_processing/validation/redundant_sql_validation_prompt.py](/config/data_processing/validation/redundant_sql_validation_prompt.py) | Python | 182 | 0 | 60 | 242 |
| [config/data_processing/validation/validation_prompts.py](/config/data_processing/validation/validation_prompts.py) | Python | 493 | 0 | 13 | 506 |
| [config/data_processing/workflow/workflow_config.py](/config/data_processing/workflow/workflow_config.py) | Python | 288 | 0 | 63 | 351 |
| [config/llm/__init__.py](/config/llm/__init__.py) | Python | 7 | 0 | 2 | 9 |
| [config/llm/llm_config.py](/config/llm/llm_config.py) | Python | 127 | 0 | 28 | 155 |
| [config/llm/prompts.py](/config/llm/prompts.py) | Python | 142 | 0 | 30 | 172 |
| [config/rl/data_conversion/orm2sql_prompt_template.py](/config/rl/data_conversion/orm2sql_prompt_template.py) | Python | 112 | 0 | 26 | 138 |
| [config/training/__init__.py](/config/training/__init__.py) | Python | 1 | 0 | 0 | 1 |
| [config/training/data_conversion/__init__.py](/config/training/data_conversion/__init__.py) | Python | 1 | 0 | 0 | 1 |
| [config/training/data_conversion/orm2sql_prompt_template.py](/config/training/data_conversion/orm2sql_prompt_template.py) | Python | 74 | 0 | 15 | 89 |
| [data_processing/__init__.py](/data_processing/__init__.py) | Python | 45 | 0 | 7 | 52 |
| [data_processing/cleaning/__init__.py](/data_processing/cleaning/__init__.py) | Python | 11 | 0 | 3 | 14 |
| [data_processing/cleaning/orm_sql_fingerprint_analyzer.py](/data_processing/cleaning/orm_sql_fingerprint_analyzer.py) | Python | 608 | 0 | 121 | 729 |
| [data_processing/cleaning/sql_cleaner.py](/data_processing/cleaning/sql_cleaner.py) | Python | 281 | 0 | 66 | 347 |
| [data_processing/converter/__init__.py](/data_processing/converter/__init__.py) | Python | 10 | 0 | 3 | 13 |
| [data_processing/converter/rl_data_converter.py](/data_processing/converter/rl_data_converter.py) | Python | 421 | 0 | 93 | 514 |
| [data_processing/converter/training_data_converter.py](/data_processing/converter/training_data_converter.py) | Python | 261 | 0 | 74 | 335 |
| [data_processing/data_analyzer.py](/data_processing/data_analyzer.py) | Python | 309 | 0 | 67 | 376 |
| [data_processing/data_reader.py](/data_processing/data_reader.py) | Python | 560 | 0 | 130 | 690 |
| [data_processing/make_data.py](/data_processing/make_data.py) | Python | 830 | 0 | 188 | 1,018 |
| [data_processing/synthetic_data_generator/__init__.py](/data_processing/synthetic_data_generator/__init__.py) | Python | 7 | 0 | 3 | 10 |
| [data_processing/synthetic_data_generator/cli.py](/data_processing/synthetic_data_generator/cli.py) | Python | 135 | 0 | 29 | 164 |
| [data_processing/synthetic_data_generator/example_usage.py](/data_processing/synthetic_data_generator/example_usage.py) | Python | 107 | 0 | 32 | 139 |
| [data_processing/synthetic_data_generator/generator.py](/data_processing/synthetic_data_generator/generator.py) | Python | 440 | 0 | 69 | 509 |
| [data_processing/synthetic_data_generator/test_generator.py](/data_processing/synthetic_data_generator/test_generator.py) | Python | 62 | 0 | 20 | 82 |
| [data_processing/validation/__init__.py](/data_processing/validation/__init__.py) | Python | 1 | 0 | 0 | 1 |
| [data_processing/validation/control_flow_validator.py](/data_processing/validation/control_flow_validator.py) | Python | 581 | 0 | 124 | 705 |
| [data_processing/validation/redundant_sql_validator.py](/data_processing/validation/redundant_sql_validator.py) | Python | 533 | 0 | 95 | 628 |
| [data_processing/validation/validator.py](/data_processing/validation/validator.py) | Python | 602 | 0 | 93 | 695 |
| [data_processing/workflow/__init__.py](/data_processing/workflow/__init__.py) | Python | 12 | 0 | 3 | 15 |
| [data_processing/workflow/workflow_manager.py](/data_processing/workflow/workflow_manager.py) | Python | 2,613 | 0 | 496 | 3,109 |
| [main.py](/main.py) | Python | 4 | 0 | 3 | 7 |
| [model/evaluation/comparative_eval/scripts/run_comparison.py](/model/evaluation/comparative_eval/scripts/run_comparison.py) | Python | 280 | 0 | 58 | 338 |
| [model/evaluation/comparative_eval/scripts/run_dataset_comparison.py](/model/evaluation/comparative_eval/scripts/run_dataset_comparison.py) | Python | 285 | 0 | 56 | 341 |
| [model/evaluation/comparative_eval/scripts/utils/response_parser.py](/model/evaluation/comparative_eval/scripts/utils/response_parser.py) | Python | 84 | 0 | 18 | 102 |
| [model/evaluation/fingerprint_eval/scripts/evaluation_report_generator.py](/model/evaluation/fingerprint_eval/scripts/evaluation_report_generator.py) | Python | 509 | 0 | 90 | 599 |
| [model/evaluation/fingerprint_eval/scripts/model_evaluator.py](/model/evaluation/fingerprint_eval/scripts/model_evaluator.py) | Python | 460 | 0 | 97 | 557 |
| [model/evaluation/fingerprint_eval/scripts/run_evaluation.py](/model/evaluation/fingerprint_eval/scripts/run_evaluation.py) | Python | 357 | 0 | 81 | 438 |
| [model/rl/code2sql_reward.py](/model/rl/code2sql_reward.py) | Python | 866 | 0 | 185 | 1,051 |
| [model/rl/composite_reward.py](/model/rl/composite_reward.py) | Python | 782 | 0 | 170 | 952 |
| [model/rl/run_verl_training.py](/model/rl/run_verl_training.py) | Python | 240 | 0 | 52 | 292 |
| [model/training/train_qwen3_ft.py](/model/training/train_qwen3_ft.py) | Python | 192 | 0 | 47 | 239 |
| [run_dataset_viewer.py](/run_dataset_viewer.py) | Python | 33 | 0 | 6 | 39 |
| [run_workflow.py](/run_workflow.py) | Python | 61 | 0 | 17 | 78 |
| [scripts/convert_rl_data.py](/scripts/convert_rl_data.py) | Python | 117 | 0 | 32 | 149 |
| [scripts/convert_training_data.py](/scripts/convert_training_data.py) | Python | 32 | 0 | 10 | 42 |
| [scripts/data_format_aligner.py](/scripts/data_format_aligner.py) | Python | 162 | 0 | 45 | 207 |
| [synthetic_data_example.py](/synthetic_data_example.py) | Python | 184 | 0 | 47 | 231 |
| [test_sglang_curl.py](/test_sglang_curl.py) | Python | 194 | 0 | 31 | 225 |
| [test_visualization.py](/test_visualization.py) | Python | 128 | 0 | 12 | 140 |
| [tests/__init__.py](/tests/__init__.py) | Python | 1 | 0 | 0 | 1 |
| [tests/test_control_flow_validation.py](/tests/test_control_flow_validation.py) | Python | 485 | 0 | 46 | 531 |
| [tests/test_data_cleaning_example.py](/tests/test_data_cleaning_example.py) | Python | 103 | 0 | 31 | 134 |
| [tests/test_keyword_extraction.py](/tests/test_keyword_extraction.py) | Python | 226 | 0 | 75 | 301 |
| [tests/test_llm_servers.py](/tests/test_llm_servers.py) | Python | 200 | 0 | 41 | 241 |
| [tests/test_redundant_validation.py](/tests/test_redundant_validation.py) | Python | 85 | 0 | 25 | 110 |
| [utils/__init__.py](/utils/__init__.py) | Python | 3 | 0 | 1 | 4 |
| [utils/format_validators.py](/utils/format_validators.py) | Python | 695 | 0 | 127 | 822 |
| [utils/llm_client.py](/utils/llm_client.py) | Python | 198 | 0 | 37 | 235 |
| [utils/preprocess.py](/utils/preprocess.py) | Python | 47 | 0 | 13 | 60 |
| [utils/response_parser.py](/utils/response_parser.py) | Python | 171 | 0 | 36 | 207 |
| [utils/sql_feature_extractor.py](/utils/sql_feature_extractor.py) | Python | 1,944 | 0 | 324 | 2,268 |
| [utils/workflow_visualizer.py](/utils/workflow_visualizer.py) | Python | 340 | 0 | 68 | 408 |
| [web_server/main.py](/web_server/main.py) | Python | 1,616 | 0 | 246 | 1,862 |

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)
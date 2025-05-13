setup:
	@if [ ! -d prompts ]; then \
	  mkdir -p prompts; \
	fi
	@if [ ! -f prompts/author.txt ]; then \
	  touch prompts/author.txt; \
	fi
	@if [ ! -f prompts/general_prompt.txt ]; then \
	  touch prompts/general_prompt.txt; \
	fi
	@if [ ! -f prompts/text_system_prompt.txt ]; then \
	  touch prompts/text_system_prompt.txt; \
	fi
	@if [ ! -f prompts/vision_system_prompt.txt ]; then \
	  touch prompts/vision_system_prompt.txt; \
	fi
	@if [ ! -d history ]; then \
	  mkdir -p history; \
	fi

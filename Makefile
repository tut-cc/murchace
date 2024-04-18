# Install the binary from
# https://github.com/tailwindlabs/tailwindcss/releases/latest
# https://tailwindcss.com/blog/standalone-cli
TAILWIND_BIN = ./tailwindcss
TEMPL_BIN = templ
GO_BIN = go

# NOTE: This function does recursive wildcard expansion. Although it works in
# the first run, the expansion does not happen lazily, leading to the situation
# where newly created go programs in the `go-watch` recipe are not being
# watched.
rwildcard=$(foreach d,$(wildcard $1*),$(call rwildcard,$d/,$2) $(filter $(subst *,%,$2),$d))

.PHONY: help
help:
	@echo "make [command]"
	@echo ""
	@echo "Commands"
	@echo "    build: unimplemented"
	@echo "    watch"
	@echo "    clean: unimplemented"

.PHONY: build
build: tailwind-build templ-build go-build

.PHONY: watch
watch:
	$(MAKE) -j tailwind-watch templ-watch go-watch

.PHONY: tailwind-build
tailwind-build:
	$(TAILWIND_BIN) --minify -i styles.css -o static/styles.css

.PHONY: tailwind-watch
tailwind-watch:
	$(TAILWIND_BIN) --watch -i styles.css -o static/styles.css

.PHONY: templ-build
templ-build:
	$(TEMPL_BIN) generate

.PHONY: templ-watch
templ-watch:
	$(TEMPL_BIN) generate -watch

.PHONY: go-build
go-build:
	$(GO_BIN) build -o order-notifier main.go

.PHONY: go-watch
go-watch:
	while true; do ls -d $(call rwildcard,,*.go) | entr -dr $(GO_BIN) run .; done

.PHONY: clean
clean:
	@echo $(call rwildcard,components/,*_templ.go)
	#@echo $(call rwildcard,,*.go)
	@echo $(call rwildcard,public/,*)

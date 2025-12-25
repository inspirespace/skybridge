PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin

.PHONY: install uninstall

install:
	@mkdir -p "$(BINDIR)"
	@install -m 0755 cloudahoy2flysto "$(BINDIR)/cloudahoy2flysto"
	@echo "Installed cloudahoy2flysto to $(BINDIR)"

uninstall:
	@rm -f "$(BINDIR)/cloudahoy2flysto"
	@echo "Removed cloudahoy2flysto from $(BINDIR)"

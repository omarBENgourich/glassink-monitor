.DEFAULT_GOAL := pdf

DIAGRAMS := architecture-industrielle deploiement-securite flux-node-red \
            logique-disponibilite modele-donnees pipeline-donnees

.PHONY: pdf diagrams clean render

diagrams:
	@for name in $(DIAGRAMS); do \
		(cd diagrams && xelatex -interaction=nonstopmode -halt-on-error "$$name.tex" >/dev/null) || exit 1; \
	done
	@echo "Schémas TikZ compilés."

pdf: diagrams
	latexmk -pdf -interaction=nonstopmode -halt-on-error rapport.tex
	@mkdir -p build
	@cp rapport.pdf build/GlassInk-Monitor-Rapport-PFA.pdf
	@echo "PDF: build/GlassInk-Monitor-Rapport-PFA.pdf"

render: pdf
	@mkdir -p build/pages
	pdftoppm -png -r 110 build/GlassInk-Monitor-Rapport-PFA.pdf build/pages/page

clean:
	latexmk -C rapport.tex
	@for name in $(DIAGRAMS); do \
		(cd diagrams && latexmk -C "$$name.tex" >/dev/null); \
	done

from fastapi import Request
from htpy import Element, HTMLElement, Node, body, head, html, link, meta, script
from htpy import title as title_elt
from markupsafe import Markup

from .env import DEBUG


def page_layout(
    req: Request,
    inner: Node,
    title: str = "murchace",
    head_section: list[Element] | None = None,
) -> HTMLElement:
    icon_url = req.url_for("static", path="/favicon.ico")
    datastar_url = req.url_for("static", path="datastar.js")
    css_url = req.url_for("static", path="/styles.css" if DEBUG else "/styles.min.css")

    return html(lang="ja")[
        head[
            meta(charset="UTF-8"),
            meta(name="viewport", content="width=device-width,initial-scale=1.0"),
            title_elt[title],
            link(rel="icon", type="image/x-icon", href=str(icon_url)),
            script(type="module", src=str(datastar_url)),
            link(rel="stylesheet", href=str(css_url)),
            head_section,
        ],
        body[inner],
    ]


clock: list[Element] = [
    Element("hh-mm-ss-clock")(class_="font-mono")["XX:XX:XX"],
    script[
        Markup(
            """
                (() => {
                  class Clock extends HTMLElement {
                    connectedCallback() {
                      this.updateClock()
                      setTimeout(
                        () => {
                          setInterval(() => this.updateClock(), 1000)
                          this.updateClock()
                        },
                        1000 - new Date().getMilliseconds()
                      )
                    }
                    updateClock() {
                      this.textContent = new Date().toTimeString().split(' ')[0]
                    }
                  }
                  customElements.define('hh-mm-ss-clock', Clock)
                })()
            """
        )
    ],
]

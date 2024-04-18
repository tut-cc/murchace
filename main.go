package main

import (
	"fmt"
	"net/http"
	"os"

	"github.com/a-h/templ"

	"order-notifier/components"
	"order-notifier/handlers"
)

func main() {
	// Do I need...
	// - grouping?
	// - middleware?
	//   Defninitely! Especially for logging and authentication.
	// Apparently, grouping and middleware comes hand in hand. The grouping
	// provides a clear separation between the different settings for
	// middlewares.

	fileServer := http.FileServer(http.Dir("./static"))
	http.Handle("GET /static/", http.StripPrefix("/static", fileServer))

	component := components.Layout(components.Hello("world"), "home")

	http.Handle("/", templ.Handler(component))
	http.Handle("GET /order", handlers.NewGetOrder())
	// http.Handle("PUT /order/{order_id}/list-item/{item_id}", nil)
	// strconv.Atoi(request.PathValue("order_id"))
	// strconv.Atoi(request.PathValue("item_id"))
	// http.Handle("DELETE /order/{order_id}/list-index/{index}", nil)
	// strconv.Atoi(request.PathValue("order_id"))
	// strconv.Atoi(request.PathValue("index"))

	// http.Handle("POST /order", handlers.NewOrder().ServeHTTP)
	// http.Handle("GET /feed", handlers.NewFeed().ServeHTTP)
	// http.Handle("GET /summary", handlers.NewSummary().ServeHTTP)

	fmt.Println("Listening on :3000")
	err := http.ListenAndServe(":3000", nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Serve error: %v\n", err)
	}
}

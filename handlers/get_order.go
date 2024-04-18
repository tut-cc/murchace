package handlers

import (
	"net/http"
	"order-notifier/components"
)

type GetOrder struct{}

func NewGetOrder() *GetOrder {
	return &GetOrder{}
}

func (h *GetOrder) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	imgs := []components.Product{
		{Id: 1, Name: "ブレンドコーヒー", Url: "/static/coffee01_blend.png"},
		{Id: 2, Name: "アメリカンコーヒー", Url: "/static/coffee02_american.png"},
		{Id: 3, Name: "カフェオレコーヒー", Url: "/static/coffee03_cafeole.png"},
		{Id: 4, Name: "ブレンドブラックコーヒー", Url: "/static/coffee04_blend_black.png"},
		{Id: 5, Name: "カプチーノコーヒー", Url: "/static/coffee05_cappuccino.png"},
		{Id: 6, Name: "カフェラテコーヒー", Url: "/static/coffee06_cafelatte.png"},
		{Id: 7, Name: "マキアートコーヒー", Url: "/static/coffee07_cafe_macchiato.png"},
		{Id: 8, Name: "モカコーヒー", Url: "/static/coffee08_cafe_mocha.png"},
		{Id: 9, Name: "カラメルコーヒー", Url: "/static/coffee09_caramel_macchiato.png"},
		{Id: 10, Name: "アイスコーヒー", Url: "/static/coffee10_iced_coffee.png"},
		{Id: 11, Name: "アイスミルクコーヒー", Url: "/static/coffee11_iced_milk_coffee.png"},
		{Id: 12, Name: "エスプレッソコーヒー", Url: "/static/coffee12_espresso.png"},

		{Id: 13, Name: "レモンティー", Url: "/static/tea_lemon.png"},
		{Id: 14, Name: "ミルクティー", Url: "/static/tea_milk.png"},
		{Id: 15, Name: "ストレイトティー", Url: "/static/tea_straight.png"},

		{Id: 16, Name: "シュガー", Url: "/static/cooking_sugar_stick.png"},
		{Id: 17, Name: "ミルクシロップ", Url: "/static/sweets_milk_cream.png"},
	}

	c := components.Order(imgs)
	err := components.Layout(c, "order").Render(r.Context(), w)

	if err != nil {
		http.Error(w, "Error rendering template", http.StatusInternalServerError)
		return
	}
}

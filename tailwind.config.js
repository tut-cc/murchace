// https://tailwindcss.com/docs/content-configuration
// const colors = require('tailwindcss/colors')
const plugin = require('tailwindcss/plugin')

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    'app/templates/**/*.html',
  ],
  // theme: {
  //   extend: {
  //     colors: {
  //       primary: colors.blue,
  //       secondary: colors.yellow,
  //       neutral: colors.gray,
  //     }
  //   },
  // },
  plugins: [
    plugin(function({ addVariant }) {
      addVariant('htmx-settling', ['&.htmx-settling', '.htmx-settling &'])
      addVariant('htmx-request',  ['&.htmx-request',  '.htmx-request &' ])
      addVariant('htmx-swapping', ['&.htmx-swapping', '.htmx-swapping &'])
      addVariant('htmx-added',    ['&.htmx-added',    '.htmx-added &'   ])
    }),
  //   require('@tailwindcss/forms'),
  //   require('@tailwindcss/typography'),
  ]
}

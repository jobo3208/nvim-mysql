" this file contains optional, opinionated autocomplete settings

" longest is what allows us to start autocomplete and then keep typing letters to narrow the search
" (only longest allows this)

set completeopt=longest,menuone

" typically, when using the longest option, no menu item is automatically highlighted.
" these settings will cause the first menu item (or, in the case of <C-p>, the last) to
" be automatically highlighted.

inoremap <expr> <C-n> pumvisible() ? '<C-n>' : '<C-n><C-r>=pumvisible() ? "\<lt>Down>" : ""<CR>'
inoremap <expr> <C-p> pumvisible() ? '<C-p>' : '<C-p><C-r>=pumvisible() ? "\<lt>Up>" : ""<CR>'
inoremap <expr> <C-x><C-u> pumvisible() ? '<C-x><C-u>' : '<C-x><C-u><C-r>=pumvisible() ? "\<lt>Down>" : ""<CR>'

" i don't remember why this was necessary, but it doesn't seem to be right now.
" inoremap <expr> <CR> pumvisible() ? "\<C-y>" : "\<C-g>u\<CR>"

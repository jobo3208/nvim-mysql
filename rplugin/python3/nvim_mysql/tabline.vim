function MySQLTabLine()
  let s = ''
  for i in range(tabpagenr('$'))
    " select the highlighting
    if i + 1 == tabpagenr()
      let s .= '%#TabLineSel#'
    else
      let s .= '%#TabLine#'
    endif

    " set the tab page number (for mouse clicks)
    let s .= '%' . (i + 1) . 'T'

    " the label is made by MySQLTabLabel()
    let s .= ' %{MySQLTabLabel(' . (i + 1) . ')} '
  endfor

  " after the last tab fill with TabLineFill and reset tab page nr
  let s .= '%#TabLineFill#%T'

  " right-align the label to close the current tab page
  if tabpagenr('$') > 1
    let s .= '%=%#TabLine#%999XX'
  endif

  return s
endfunction

function MySQLTabLabel(n)
  let buflist = tabpagebuflist(a:n)
  let winnr = tabpagewinnr(a:n)
  let bufnum = buflist[winnr - 1]
  let name =  bufname(bufnum)
  let modified = getbufvar(bufnum, "&mod")

  if name == ""
    let name = "[No Name]"
  endif

  if modified == 1
    let name = "+ " . name
  endif

  let server = gettabvar(a:n, "MySQLServer")
  let status_flag = gettabvar(a:n, "MySQLStatusFlag")
  if server != ""
    let name .= " (" . server
    if status_flag != ""
      let name .= " [" . status_flag . "]"
    endif
    let name .= ")"
  endif

  return name
endfunction

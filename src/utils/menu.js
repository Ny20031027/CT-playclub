export const normalizeMenuPath = (path) => {
  if (!path) return ''
  return path.startsWith('/') ? path : `/${path}`
}

export const flattenMenuTree = (menus = []) => {
  const result = []

  const walk = (items = []) => {
    items.forEach((item) => {
      if (!item) return
      const normalizedPath = normalizeMenuPath(item.path)
      if (normalizedPath) {
        result.push({
          ...item,
          path: normalizedPath,
        })
      }
      if (item.children && item.children.length) {
        walk(item.children)
      }
    })
  }

  walk(menus)
  return result
}

export const getMenuPaths = (menus = []) => {
  return flattenMenuTree(menus)
    .map((item) => item.path)
    .filter(Boolean)
}

export const getFirstMenuPath = (menus = [], fallback = '/dashboard') => {
  const paths = getMenuPaths(menus)
  return paths.length ? paths[0] : fallback
}

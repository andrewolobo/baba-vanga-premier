// How many settled calls /results asks for. In one place because the loader
// and the page's toggle must ask for the same number: a default in the
// loader that the toggle did not match would refetch a different list on
// hydration, for nothing.
//
// 60 is the API's own default for `/tips/results` (api/main.py), and 500 is
// its ceiling — it 400s above that, so "show all" means "up to the server
// max", not "everything there will ever be".
export const DEFAULT_LIMIT = 60;
export const MAX_LIMIT = 500;

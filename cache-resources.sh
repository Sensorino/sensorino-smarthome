#! /bin/bash
#
# Download current versions of external resources used by the HTML5
# user interface (i.e. external JavaScript libraries) and cache them
# locally and make index.xhtml point at the local copies for faster
# loading.  Note the UI will probably still make external HTTP request
# because we're using Google Charts which is Google's API loads
# dynamically...

HTTP_ROOT=static
CACHE_PATH=cache

# TODO: use python+cElementTree or, if HTML support needed,
# python2+libtidy and python3+html.parse/html5lib
grep 'src="[^"]*//.*"' "$HTTP_ROOT"/*html | while read line; do
	[ -z "$line" ] && break

	src=${line#*src=\"} # Drop everything before the URL
	src=${src%\"*} # Drop everything after the URL

	url=$src
	[ "${url#//}" = "${url}" ] || url=http:$url

	mkdir -p "$HTTP_ROOT/$CACHE_PATH"
	new_src=$CACHE_PATH/`basename "$url"`
	filename=$HTTP_ROOT/$new_src

	echo Downloading "$url" to "$filename"
	# NOTE: -k disables certificate checks, INSECURE
	curl -k -L -o "$filename" "$url" || continue

	sed -i -e s^src=\""$src"\"^src=\""$new_src"\"^ "$HTTP_ROOT"/*html
done

# ZonalStats API


## Method

`POST`


## Request Payload

```

`aoi`: <geojson geometry; valid geojson and valid geometry.  Polygon or Multipolygon>

`image`: {
    `url`: <url to COG (or other cloud native format)>,
    `bands`: <list of band indices; default to band 1>,
    `approx_stats`: <true/false; default to true
 }

`stac`: {
    `url`: <url to STAC item>,
    `asset`: <asset id; default: guess which asset else exception>,
    `bands`: <list of band indices; default to band 1>,
    `approx_stats`: <true/false; default to true>
}

`stats`: <list of stats type to calculate>
    options: "area", "count", "max", "mean", "median", "min", "std_dev", "sum", "freq_hist"
    default: "area", "count", "max", "mean", "median", "min", "std_dev", "sum"  

```

## Response

Here's a sample response but if there's a clearer, simpler way of representing the results this can be changed.

```
{
    "<band x>::{
        "area": <Area of raster with the AOI>,
        "count": <number>,
        "max": <number>,
        "mean": <number>,
        "median": <number>,
        "min": <number>,
        "std_dev": <number>,
        "sum": <number>
    }
}
```


## Notes

* The expectation that the zonal stats are calculated dynamically.
* aoi is required
* image or stac is required.  If both are added raise 400 error
    
    * prioritize support for `image` in the request parameters
* `approx_stats`: Will use overviews in the case of COG to calculate zonal stats.
* Rate limit and quotas:
    
    * Limit on polygon size (TBD: number of vertices, area, other??)

* keep docker image small
* FastAPI based
* will be running on a lambda
* no need to for any devops setup (CDK, other)



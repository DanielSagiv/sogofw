#include <gst/gst.h>
#include <glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <glib-unix.h>

//message processing
static gboolean bus_call(GstBus * bus, GstMessage * msg, gpointer data)
{
  GMainLoop *loop = (GMainLoop *) data;

  switch (GST_MESSAGE_TYPE(msg))
  {
    case GST_MESSAGE_EOS:
      g_print("End of stream\n");
      g_main_loop_quit(loop);
      break;
    case GST_MESSAGE_ERROR:
    {
      gchar *debug;
      GError *error;
      gst_message_parse_error(msg, &error, &debug);
      g_free(debug);
      g_printerr("ERROR:%s\n", error->message);
      g_error_free(error);
      g_main_loop_quit(loop);
      break;
    }
    default:
      break;
}

  return 1;
}

void on_pad_added (GstElement *element, GstPad *pad, gpointer data)
{
  GstPad *sinkpad;
  GstElement *decoder = (GstElement *) data;
  /* We can now link this pad with the vorbis-decoder sink pad */
  g_print ("Dynamic pad created, linking demux/decoder\n");
  sinkpad = gst_element_get_static_pad (decoder, "sink");
  gst_pad_link (pad, sinkpad);
  gst_object_unref (sinkpad);
}

static gboolean intr_handler (GstElement * pipeline)
{
  GST_DEBUG_BIN_TO_DOT_FILE_WITH_TS (GST_BIN (pipeline),
      GST_DEBUG_GRAPH_SHOW_ALL, "gst-validate.interrupted");

  gst_element_send_event (pipeline, gst_event_new_eos ());
  return TRUE;
}

int camera_process (char *path)
{
  //create element, caps and bus
  GMainLoop *loop;
  GstElement *pipeline, *source, *converter, *encoder, *decoder;
  GstElement *demux, *mux, *sink, *vqueue, *parse;
  GstElement *source_capsfilter;
  GstCaps *source_caps;
  GstBus *bus;
  //char outfile[] = "/home/khadas/video.mp4";
  char outfile[80];

  memcpy(outfile, path, strlen(path));

  //initial gstreamer
  gst_init (NULL, NULL);

  //create main loop, start to loop after running g_main_loop_run
  loop = g_main_loop_new(NULL, -1);

  /* sample code for recording mipi-camera */

  //create pipeline and element
  pipeline = gst_pipeline_new("mipi-camera");
  #ifdef G_OS_UNIX
  g_unix_signal_add (SIGINT, (GSourceFunc) intr_handler, pipeline);
  #endif
  source = gst_element_factory_make("v4l2src", "camera-input");
     g_object_set (source, "num-buffers", 15 * 30, NULL); // 30s
  // set source parameters
  g_object_set(G_OBJECT(source),"device", "/dev/video42", NULL);
    // create source caps filter
  source_capsfilter = gst_element_factory_make("capsfilter", "source_capsfilter");
  source_caps = gst_caps_new_simple ("video/x-raw",
  		   "format", G_TYPE_STRING, "NV12",
  		   "width", G_TYPE_INT, 2560,
  		   "height", G_TYPE_INT, 1440,
  		   NULL);
  g_object_set(G_OBJECT(source_capsfilter),"caps", source_caps, NULL);
  // create converter element
  converter = gst_element_factory_make("videoconvert", "video-converter");
  // create H264 encoder element
  encoder = gst_element_factory_make("mpph264enc", "video-encoder");
  // create H264 parse element
  parse = gst_element_factory_make("h264parse", "video-parse");
  // create H264 MUX element
  mux = gst_element_factory_make("mp4mux", "video-mux");
  // create sink element
  sink = gst_element_factory_make("filesink", "file-storage");
  g_object_set(G_OBJECT(sink),"location", outfile, NULL);

  if (!pipeline || !source || !source_capsfilter || !converter || !encoder || !parse || !mux || !sink)
  {
     g_printerr("One element could not be created.Exiting.\n");
     return -1;
  }
  // create pipeline message bus
  bus = gst_pipeline_get_bus(GST_PIPELINE(pipeline));
  // add message monitor
  gst_bus_add_watch(bus, bus_call, loop);
  gst_object_unref(bus);

  // add elements to pipeline
  gst_bin_add_many(GST_BIN(pipeline), source, source_capsfilter, converter, encoder, parse, mux, sink, NULL);
  // connect elements sequentially
  gst_element_link_many(source, source_capsfilter, converter, encoder, parse, mux, sink, NULL);

  //led_show(TRUE);

  // star to play
  gst_element_set_state(pipeline, GST_STATE_PLAYING);
  g_print("Running\n");

  // start to loop
  g_main_loop_run(loop);

  // quit loop and return
  g_print("Returned,stopping playback\n");
  gst_element_set_state(pipeline, GST_STATE_NULL);
  gst_object_unref(GST_OBJECT(pipeline));

  //led_show(FALSE);

  return 0;
}

import 'package:http/http.dart' as http;
import 'dart:convert';
import 'models/talk.dart';

Future<List<Talk>> initEmptyList() async {

  Iterable list = json.decode("[]");
  var talks = list.map((model) => Talk.fromJSON(model)).toList();
  return talks;

}

Future<List<Talk>> getTalksByTag(String tag, int page) async {
  var url = Uri.parse('https://5o5ookrro7.execute-api.us-east-1.amazonaws.com/default/Get_Talks_By_Tag');

  final http.Response response = await http.post(url,
    headers: <String, String>{
      'Content-Type': 'application/json',
    },
    body: jsonEncode(<String, Object>{
      'tag': tag,
      'page': page,
      'doc_per_page': 6
    }),
  );
  if (response.statusCode == 200) {
    final body = utf8.decode(response.bodyBytes);
    final List<dynamic> jsonList = json.decode(body);
    return jsonList.map((json) => Talk.fromJSON(json)).toList();
  } else if (response.statusCode == 404) {
    throw Exception('Nessun talk trovato per questo tag');
  } else {
    throw Exception('Errore nel caricamento dei talk');
  }
      
}

Future<List<Talk>> getWatchNext(String id) async {
  var url = Uri.parse('https://fw6i63pnnd.execute-api.us-east-1.amazonaws.com/default/Get_Watch_Next_by_Idx');

  final http.Response response = await http.post(url,
    headers: <String, String>{
      'Content-Type': 'application/json',
    },
    body: jsonEncode(<String, Object>{
      'id': id,
      'page': 1,
      'doc_per_page': 1000
    }),
  );
  if (response.statusCode == 200) {
    final body = utf8.decode(response.bodyBytes);
    final Map<String, dynamic> jsonMap = json.decode(body);
    final List<dynamic> relatedVideos = jsonMap['related_videos'] ?? [];
    return relatedVideos.map((json) => Talk.fromJSON(json)).toList();
  } else if (response.statusCode == 404) {
    throw Exception('Il talk cercato non esiste');
  } else {
    throw Exception('Errore nel caricamento dei consigli');
  }
}
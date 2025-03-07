// Copyright (C) 2019-2020 Zilliz. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software distributed under the License
// is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
// or implied. See the License for the specific language governing permissions and limitations under the License.

package storage

import (
	"bytes"
	"encoding/binary"
	"errors"
	"io"

	"github.com/milvus-io/milvus/internal/proto/etcdpb"
)

type VectorChunkManager struct {
	localChunkManager  ChunkManager
	remoteChunkManager ChunkManager

	schema *etcdpb.CollectionMeta

	localCacheEnable bool
}

func NewVectorChunkManager(localChunkManager ChunkManager, remoteChunkManager ChunkManager, schema *etcdpb.CollectionMeta, localCacheEnable bool) *VectorChunkManager {
	return &VectorChunkManager{
		localChunkManager:  localChunkManager,
		remoteChunkManager: remoteChunkManager,

		schema:           schema,
		localCacheEnable: localCacheEnable,
	}
}

func (vcm *VectorChunkManager) downloadVectorFile(key string) ([]byte, error) {
	if vcm.localChunkManager.Exist(key) {
		return vcm.localChunkManager.Read(key)
	}
	insertCodec := NewInsertCodec(vcm.schema)
	content, err := vcm.remoteChunkManager.Read(key)
	if err != nil {
		return nil, err
	}
	blob := &Blob{
		Key:   key,
		Value: content,
	}

	_, _, data, err := insertCodec.Deserialize([]*Blob{blob})
	if err != nil {
		return nil, err
	}
	defer insertCodec.Close()

	var results []byte
	for _, singleData := range data.Data {
		binaryVector, ok := singleData.(*BinaryVectorFieldData)
		if ok {
			results = binaryVector.Data
		}
		floatVector, ok := singleData.(*FloatVectorFieldData)
		if ok {
			buf := new(bytes.Buffer)
			err := binary.Write(buf, binary.LittleEndian, floatVector.Data)
			if err != nil {
				return nil, err
			}
			results = buf.Bytes()
		}
	}
	return results, nil
}

func (vcm *VectorChunkManager) GetPath(key string) (string, error) {
	if vcm.localChunkManager.Exist(key) && vcm.localCacheEnable {
		return vcm.localChunkManager.GetPath(key)
	}
	return vcm.remoteChunkManager.GetPath(key)
}

func (vcm *VectorChunkManager) Write(key string, content []byte) error {
	if !vcm.localCacheEnable {
		return errors.New("Cannot write local file for local cache is not allowed")
	}
	return vcm.localChunkManager.Write(key, content)
}

func (vcm *VectorChunkManager) Exist(key string) bool {
	return vcm.localChunkManager.Exist(key)
}

func (vcm *VectorChunkManager) Read(key string) ([]byte, error) {
	if vcm.localCacheEnable {
		if vcm.localChunkManager.Exist(key) {
			return vcm.localChunkManager.Read(key)
		}
		bytes, err := vcm.downloadVectorFile(key)
		if err != nil {
			return nil, err
		}
		err = vcm.localChunkManager.Write(key, bytes)
		if err != nil {
			return nil, err
		}
		return vcm.localChunkManager.Read(key)
	}
	return vcm.downloadVectorFile(key)
}

func (vcm *VectorChunkManager) ReadAt(key string, p []byte, off int64) (int, error) {
	if vcm.localCacheEnable {
		if vcm.localChunkManager.Exist(key) {
			return vcm.localChunkManager.ReadAt(key, p, off)
		}
		bytes, err := vcm.downloadVectorFile(key)
		if err != nil {
			return -1, err
		}
		err = vcm.localChunkManager.Write(key, bytes)
		if err != nil {
			return -1, err
		}
		return vcm.localChunkManager.ReadAt(key, p, off)
	}
	bytes, err := vcm.downloadVectorFile(key)
	if err != nil {
		return -1, err
	}

	if bytes == nil {
		return 0, errors.New("vectorChunkManager: data downloaded is nil")
	}

	if off < 0 || int64(len(bytes)) < off {
		return 0, errors.New("vectorChunkManager: invalid offset")
	}
	n := copy(p, bytes[off:])
	if n < len(p) {
		return n, io.EOF
	}

	return n, nil
}
